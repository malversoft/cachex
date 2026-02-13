# -*- coding: utf-8 -*-


import functools, inspect, types

from .DecoratorHelper import DecoratorHelper
from .CacheKeyHelper import CacheKeyHelper
from .CacheDescription import CacheDescription
from .CacheParameters import CacheParameters
from .CachedException import CachedException, NonException


# When caching an unbound method, by default the accessors would not work correctly when the object is bounded,
# because in the bound method the attributes would point to the unbound version of the accessors.
# To ammend this, wrapper descriptors must be used to deal with unbound methods.


class FunctionWrapper():
	"""
	Wrapper descriptor for function.
	Unlike Python builtin function/method objects, this allows to attach any attribute to it.
	"""

	# Map properties with corresponding accessor function.
	@property
	def cache(self):
		return self._cache()
	@property
	def cache_lock(self):
		return self._cache_lock()

	def __init__(self, function, attrs = {}):
		self._cache_wrapped_function = function
		for attr in attrs:
			setattr(self, attr, attrs[attr])
	# Pass through '__self__', '__func__' and any other attributes of bound method.
	# Pass through '__name__', '__qualname__' and any other attributes of unbound function.
	def __getattr__(self, attr):
		return getattr(self._cache_wrapped_function, attr)
	# Must be callable.
	def __call__(self, *args, **kwargs):
		return self._cache_wrapped_function(*args, **kwargs)


class BoundMethodWrapper(FunctionWrapper):
	"""
	Wrapper descriptor for bound method.
	"""
	# Must be callable.
	def __call__(self, *args, **kwargs):
		return self._cache_wrapped_function.__func__(*args, **kwargs)


class UnboundMethodWrapper(FunctionWrapper):
	"""
	Wrapper descriptor for unbound method.
	When referenced as a bound method of an instance, binds also the accessors to the instance
	and provides a wrapper of the bound method with the accessors bound and attached.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.__cache_module = self._cache_wrapped_function.__module__
	# Descriptor getter.
	def __get__(self, obj, objtype=None):
		bound_method = self._bind_method(obj, objtype, self._cache_wrapped_function)		# Bind method.
		if inspect.ismethod(bound_method):
			# Descriptor is being referenced as a bound method of a class or instance.
			attrs_to_bind = (
				'uncached', '_cache', '_cache_lock', 'cache_key', 'cache_clear', 'cache_info',
				'cache_parameters', 'cache_configuration',
			)
			attrs_not_to_bind = (
			)
			obj = bound_method.__self__
			attrs = {
				attr : getattr(self._cache_wrapped_function, attr).__get__(obj, None)
				for attr in (attrs_to_bind)
			}
			attrs.update({
				attr : getattr(self._cache_wrapped_function, attr)
				for attr in (attrs_not_to_bind)
			})
			# Setup bound method wrapper with attributes set.
			bound_method = BoundMethodWrapper(bound_method, attrs)
			bound_method.__module__ = self.__cache_module		# Fake the module name as the original.
			# Return bound method, so it validates against inspect.ismethod() and similar type comparisons.
			bound_method = types.MethodType(bound_method, obj)
		return bound_method
	# Bind method to instance.
	def _bind_method(self, obj, objtype, method):
		return method.__get__(obj, objtype)


class ClassMethodWrapper(UnboundMethodWrapper):
	"""
	Wrapper descriptor for unbound class method.
	Accessors are not bounded by default because Python classmethod descriptor does not invoke '__get__'
	on the underlying function descriptor when bounding a class method.
	This wrapper fakes the Python classmethod descriptor to do exactly that.
	When referenced as a bound method of a class or instance, binds also the accessors to the class
	and provides a wrapper of the bound method with the accessors bound and attached.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.__cache_classmethod = classmethod(self._cache_wrapped_function)
	# Bind method to class.
	def _bind_method(self, obj, objtype, method):
		return super()._bind_method(obj, objtype, self.__cache_classmethod)


class FunctionDefinition():
	"""Function characterization."""

	def __init__(self, func, transformer):

		if isinstance(func, classmethod):
			raise ValueError('Cannot cache classmethod. Use @cached.classmethod instead of @classmethod.')
		elif isinstance(func, staticmethod):
			raise ValueError('Cannot cache staticmethod. Use @cached.staticmethod instead of @staticmethod.')
		elif not callable(func):
			raise TypeError('Expected function to cache, got %s instead.' % type(func).__name__)

		self.isboundmethod = inspect.ismethod(func)
		# If function is a bound method unwrap it,
		# so the wrapped call accepts all the arguments passed to the wrapper (including 'self' or 'cls').
		self.call = func.__func__ if self.isboundmethod else func
		self.arg_names = list(inspect.signature(self.call).parameters)

		try:
			try:
				# Check if fake classmethod transformer.
				self.isclassmethod = transformer.isclassmethod
				self.arg_self = self.arg_names[0]
			except AttributeError:
				self.isclassmethod = False
				if transformer is property:
					self.arg_self = self.arg_names[0]
				else:
					self.arg_self = self.arg_names[0] if self.arg_names[0] in DecoratorHelper.defaults._arg_self else None
		except IndexError:
			self.arg_self = None
		self.isunboundmethod = bool(self.arg_self)

	def __repr__(self):
		return '%s(%r)' % (type(self).__name__, self.__dict__)


class Decorator():
	"""Decorator creator."""

	decorator = None

	def __call__(self, func):
		return self.decorator(func)

	def __init__(self, cache,
		typed = None, exceptions = None, stateful = None, shared = None,
		key = None, lock = None,	# Compatibility with cachetools 'cached' decorator.
		_transformer = None
	):

		# Normalize and parse decorator parameters.
		# Use reusable copy of parameters.

		_config = locals()
		del _config['self']
		_config = CacheParameters.bind(self.__init__, **_config)
		_config_irrelevant = ['_transformer']
		_cache = _config.cache

		_config['typed'] = bool(_config.typed)

		# Compatibility with cachetools 'key' argument.
		if _config.key:
			_config['typed'] = CacheKeyHelper.get_typed_from_key(_config.key)		# True, False or None.
			_config_irrelevant.append('typed')
		else:
			_config_irrelevant.append('key')

		# Determine exceptions to be cached.
		exceptions = _config.exceptions
		if exceptions:
			try:
				exceptions_iter = iter(exceptions)
			except Exception:
				if not (isinstance(exceptions, type) and issubclass(exceptions, Exception)):
					exceptions = Exception
			else:
				exceptions = tuple([e for e in exceptions_iter if isinstance(e, type) and issubclass(e, Exception)]) or None
		if not exceptions:
			exceptions = NonException

		# Decorator function.

		def decorator(func):

			# Allow to reuse decorator.

			config = _config.copy()
			config_irrelevant = _config_irrelevant.copy()
			cache = DecoratorHelper.get_cache_instance(_cache)

			# Characterize function.

			funcdef = FunctionDefinition(func, _transformer)

			# Prepare accessors.

			if funcdef.isboundmethod or funcdef.isunboundmethod:
				check_accessor_allowed = lambda accessor_desc, accessor_func: None
			else:
				def check_accessor_allowed(accessor_desc, accessor_func):
					# Cached function must be a bound or unbound method to use accessors with arguments.
					raise ValueError('%s getter with object argument used in non-method function: %s.' % (accessor_desc.capitalize(), DecoratorHelper.accessor_name(accessor_func),))
				config_irrelevant.append('stateful')

			funcname = func.__name__
			funcargself = funcdef.arg_self
			def get_self(*args):
				try:
					return args[0]
				except IndexError:
					raise TypeError("%s() missing 1 required positional argument%s." % (funcname, funcargself and ": '%s'" % (funcargself,) or '',))

			def get_accessor(accessor_func, accessor_desc):
				# Given a callable function that provides a resource, analyze if it gets the resource
				# from the bounded instance/class or from a source independent of the instance/class.
				# Returns the simplest possible accessor function to the resource,
				# and also a flag indicating if it is dependent on the instance/class.

				if isinstance(accessor_func, classmethod):
					# Special case where the accessor is a decorated classmethod of the same class.
					is_dependent = True
					accessor_classmethod = accessor_func.__get__(0, None)
					check_accessor_allowed(accessor_desc, accessor_classmethod)
					accessor_nargs = DecoratorHelper.has_args(accessor_classmethod)
					if accessor_nargs > 0:
						# Inform cached function name to accessor function.
						def get_resource(*args):
							obj = get_self(*args)
							if isinstance(obj, type):
								# Argument is class.
								return accessor_func.__get__(None, obj)(funcname)
							else:
								# Argument is object.
								return accessor_func.__get__(obj, None)(funcname)
					elif accessor_nargs == 0:
						def get_resource(*args):
							obj = get_self(*args)
							if isinstance(obj, type):
								# Argument is class.
								return accessor_func.__get__(None, obj)()
							else:
								# Argument is object.
								return accessor_func.__get__(obj, None)()

				else:

					if isinstance(accessor_func, staticmethod):
						# Special case where the accessor is a decorated staticmethod of the same class.
						accessor_func = accessor_func.__get__(0, None)

					accessor_nargs = DecoratorHelper.has_args(accessor_func)
					if accessor_nargs:
						# Resource shared across instance/class methods.
						is_dependent = True
						check_accessor_allowed(accessor_desc, accessor_func)
						if accessor_nargs > 1:
							# Inform cached function name to accessor function.
							get_resource = lambda *args: accessor_func(get_self(*args), funcname)
						elif accessor_nargs == 1:
							get_resource = lambda *args: accessor_func(get_self(*args))

					else:
						# Resource is get from a source independent of the instance/class.
						is_dependent = False
						get_resource = lambda *args: accessor_func()

				return get_resource, is_dependent

			# Create cache accessors.

			get_cache = None
			cache_accessor = None
			shared = config.shared

			if DecoratorHelper.is_callable(shared):
				# Analize shared cache getter.

				get_cache, is_dependent = get_accessor(shared, 'shared cache')
				if not is_dependent:
					cache_accessor = lambda obj_self = None, obj_other = None: shared()

				config_irrelevant.append('cache')

			elif not shared and funcdef.isunboundmethod and not funcdef.isclassmethod:

				# Unique method cache per object instance.
				attr_cache_name = DecoratorHelper.defaults._attr_cache		# Make this fixed, as defaults may change after performing the decoration.
				def get_cache(*args):
					obj = get_self(*args)
					try:
						cstorage = getattr(obj, attr_cache_name)
					except AttributeError:
						cstorage = {}
						setattr(obj, attr_cache_name, cstorage)
					try:
						c = cstorage[funcname]
					except KeyError:
						c = cache.clone()
						cstorage[funcname] = c
					return c

			if cache_accessor is None:

				if get_cache is not None:

					def cache_accessor(obj_self = None, obj_other = None):
						if obj_other:
							# Called from bound method with argument.
							obj_self = obj_other
						if obj_self is None:
							return cache
						else:
							try:
								# If provided argument is a method, get the object instance.
								obj_self = obj_self.__self__
							except AttributeError:
								pass
							return get_cache(obj_self)

				else:

					# Function owned cache.
					get_cache = lambda *args: cache
					cache_accessor = lambda obj_self = None, obj_other = None: cache
					if not funcdef.isunboundmethod:
						config_irrelevant.append('shared')

			# Create wrapper function.

			call = funcdef.call
			key = CacheKeyHelper.make_key_func(funcdef, config)

			# Compatibility with cachetools 'lock' argument.
			lock = config.lock
			if DecoratorHelper.is_callable(lock):
				# Analyze lock getter.
				get_altlock, _ = get_accessor(lock, 'lock')
			elif lock:
				get_altlock = lambda *args: lock
			else:
				get_altlock = lambda *args: None
				config_irrelevant.append('lock')

			# Wrapper function.
			def wrapper(*args, **kwargs):
				cache = get_cache(*args)
				if cache is None:
					return call(*args, **kwargs)
				lock = get_altlock(*args) or cache.lock
				k = key(*args, **kwargs)
				try:
					with lock, cache.counters:
						v = cache[k]
					hit = True
				except KeyError:
					hit = False
					# Errors can be cached too, so avoid stacking the cache access exception.
				if not hit:
					try:
						v = call(*args, **kwargs)
					except exceptions as e:
						v = CachedException(e)
					try:
						with lock:
							cache[k] = v
					except ValueError:
						pass  # Value too large.
				if isinstance(v, CachedException):
					# Raise cached exception.
					raise v.exception
				return v

			# Setup rest of cache accessors.

			def cache_clear(obj_self=None, obj_other=None):
				cache = cache_accessor(obj_self, obj_other)
				lock = get_altlock(obj_self) or cache.lock
				with lock:
					cache.clear()
			def cache_info(obj_self=None, obj_other=None):
				cache = cache_accessor(obj_self, obj_other)
				lock = get_altlock(obj_self) or cache.lock
				with lock:
					return cache.info
			def _cache_lock(obj_self=None, obj_other=None):
				cache = cache_accessor(obj_self, obj_other)
				lock = get_altlock(obj_self) or cache.lock
				return lock
			typed = config.typed
			def cache_parameters(obj_self=None, obj_other=None):
				params = {'typed' : typed}
				params.update(cache_accessor(obj_self, obj_other).parameters)
				return params

			# Compose configuration information.

			if not 'cache' in config_irrelevant:
				# Do not actually provide the cache object with its contents, but an abstract description of it.
				# TODO: Reconsider using the cache description instead of the original cache parameter,
				#       as this avoids using the result from cache_configuration() to get an identical decorator.
				config['cache'] = CacheDescription.from_instance(cache)
				config.move_to_end('cache', last=False)

			# Only the configuration parameters that were relevant to decorate the specific function will be provided.
			for p in config_irrelevant:
				config.pop(p, None)

			# Attach function attributes and accessors.

			functools.update_wrapper(wrapper, func)

			attrs = {
				'uncached': func,					# Uncached variant of function.
				'_cache': cache_accessor,			# Access to cache object used.
				'_cache_lock': _cache_lock,			# Lock used.
				'cache_key': key,					# Key function used.
				'cache_clear': cache_clear,			# Clear the cache.
				'cache_info': cache_info,			# Cache information.
				'cache_parameters': cache_parameters,					# Cache parameters.
				'cache_configuration': lambda *args: config.copy(),		# Cache configuration accessor.
			}
			for attr in attrs:
				setattr(wrapper, attr, attrs[attr])

			# Return decorated function/method.

			if funcdef.isboundmethod:
				# Return bound method.
				return UnboundMethodWrapper(wrapper).__get__(func.__self__, None)
			elif funcdef.isclassmethod:
				# Return unbound class method.
				return ClassMethodWrapper(wrapper)
			elif funcdef.isunboundmethod:
				# Return unbound method.
				return UnboundMethodWrapper(wrapper)
			else:
				# Return function.
				return FunctionWrapper(wrapper)

		self.decorator = decorator
