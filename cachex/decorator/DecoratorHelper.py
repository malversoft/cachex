# -*- coding: utf-8 -*-


import inspect, operator, math

from .CacheDefaults import CacheDefaults
from .CacheDescription import CacheDescription
from ..caches.Helper import Helper
from .. import caches


class DecoratorHelper():
	"""Decorator helper functions."""

	defaults = CacheDefaults()

	@classmethod
	def is_standard_cache_class(cls, kls):
		kls = not isinstance(kls, type) and type(kls) or kls
		return Helper.is_cache_class(kls)

	@classmethod
	def is_cache_class(cls, kls):
		return Helper.is_converted_cache_class(kls)

	@classmethod
	def is_cache_instance(cls, obj):
		return cls.is_cache_class(type(obj))

	@classmethod
	def is_callable(cls, func):
		return (callable(func) or isinstance(func, (staticmethod, classmethod,))) and \
			not cls.is_cache_instance(func) and not cls.is_cache_class(func)

	@classmethod
	def get_cache_instance(cls, cache):
		"""Parse cache parameter and returns corresponding cache instance."""
		c = None
		if cache is False:
			# No caching.
			c = None
		elif cls.is_cache_instance(cache):
			# Specified cache instance.
			c = cache
		elif cls.is_cache_class(cache):
			# Specified cache class.
			c = cache()
		elif isinstance(cache, CacheDescription):
			# Specified cache description.
			c = cache.instantiate()
		elif cache:
			# Default cache.
			c = cls.get_default_cache_class()()
		if c is None:
			c = caches.NoCache()
			c.lock = None
		return c

	@classmethod
	def get_default_cache_class(cls):
		kls = cls.defaults._cache_class
		if not cls.is_cache_class(kls):
			# Protection against incorrectly set defaults.
			kls = caches.LRUCache
		return kls

	@classmethod
	def unbind_parameters(_cls, _func, *args, **kwargs):
		"""
		Given a function and a set of arguments, removes from the provided arguments
		the ones that correspond to the function.
		"""
		params_def = inspect.signature(_func).parameters
		for pname in params_def:
			param = params_def[pname]
			if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
				# Skip *args and **kwargs declaration in function.
				continue
			if pname in kwargs:
				del kwargs[pname]
			elif args:
				args = args[1:]
		return args, kwargs

	@classmethod
	def has_args(cls, func):
		"""Returns the number of positional arguments allowed by the specified function."""
		try:
			params_def = inspect.signature(func).parameters
		except ValueError:
			return isinstance(func, (operator.attrgetter, operator.methodcaller)) and 1 or 0
		else:
			nargs = 0
			for pname in params_def:
				param = params_def[pname]
				if param.kind is inspect.Parameter.VAR_POSITIONAL:
					# Accessor accepts positional wildcard argument *args.
					return math.inf
				elif param.kind is not inspect.Parameter.VAR_KEYWORD:
					# Discard keyword wildcard argument **kwargs, if present.
					nargs += 1
			return nargs

	@classmethod
	def accessor_name(cls, func):
		if isinstance(func, (operator.attrgetter, operator.methodcaller)):
			return str(func)
		else:
			return func.__name__
