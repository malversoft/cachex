# -*- coding: utf-8 -*-


from collections.abc import MutableMapping
import inspect

from .CacheMixin import CacheMixin
from .CacheDefaults import CacheDefaults


class CachesPool():
	pass


class Helper():
	"""Functions to help with caches conversion, caches pools and modules management."""

	attr_converted_class = '_is_converted'

	@staticmethod
	def is_cache_class(kls):
		return isinstance(kls, type) and issubclass(kls, MutableMapping)

	@classmethod
	def is_converted_cache_class(cls, kls):
		return cls.is_cache_class(kls) and getattr(kls, cls.attr_converted_class, False)

	@classmethod
	def with_module_cache_classes(cls, module, func):
		"""Perform a function (or list of functions) with all cache classes of the specified module (or list of modules)."""

		try:
			iter(module)
		except Exception:
			for k in dir(module):
				if k.startswith('_'):
					continue
				kls = getattr(module, k)
				if cls.is_cache_class(kls):
					try:
						iter(func)
					except Exception:
						func(kls)
					else:
						for f in func:
							f(kls)
		else:
			for m in iter(module):
				cls.with_module_cache_classes(m, func)

	@classmethod
	def _wrap_class(cls, kls):
		return type(kls.__name__, (CacheMixin, kls), {})

	@classmethod
	def convert_class(cls, kls):

		if not isinstance(kls, type):
			# Will also accept cache instances.
			kls = type(kls)

		if cls.is_converted_cache_class(kls):
			return kls
		elif not cls.is_cache_class(kls):
			raise TypeError('Class %s does not seem to be a cache class.' % kls.__name__)

		try:
			# Find out caller module namespace.
			# Note: Apparently this takes a bit of time (because the inspection, not the loop).
			stack = inspect.stack()
			i = 1
			while True:
				modname = inspect.getmodule(stack[i][0]).__name__
				if modname != __name__:
					break
				i += 1
		except Exception as e:
			# Default to the original class module namespace.
			modname = kls.__module__

		attrs = {
			'__module__' : modname,
			'__doc__' : kls.__doc__,
			'__name__' : kls.__name__,
			'__qualname__' : kls.__name__,	# Not the original __qualname__, as the wrapper is not a nested class.
			cls.attr_converted_class : True,
		}

		wrapper_kls = cls._wrap_class(kls)
		for a in attrs:
			setattr(wrapper_kls, a, attrs[a])

		return wrapper_kls

	@classmethod
	def add_to_pool(cls, target, kls = None, name = None):

		if kls is None:

			# Create an empty pool.
			container = CachesPool()
			cls.setup_pool(container)
			return container

		elif kls and isinstance(kls, str):

			# Add an empty pool with specified name.
			containername = kls
			container = CachesPool()
			cls.setup_pool(container)
			setattr(target, containername, container)
			return container

		elif inspect.ismodule(kls):

			# Add a module.
			mod = kls
			containername = name or mod.__name__.split('.')[-1]
			container = CachesPool()
			cls.setup_pool(container)
			setattr(target, containername, container)
			cls.with_module_cache_classes(mod, container.add)
			return container

		else:

			# Add a class.
			wrapper_kls = cls.convert_class(kls)
			containername = name or wrapper_kls.__name__
			setattr(target, containername, wrapper_kls)
			return wrapper_kls

	@classmethod
	def setup_pool(cls, container):
		container.defaults = CacheDefaults()
		container.convert = cls.convert_class
		container.add = lambda kls=None, name=None: cls.add_to_pool(container, kls, name)
