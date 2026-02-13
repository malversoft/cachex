# -*- coding: utf-8 -*-


import functools, types, inspect

from .Decorator import Decorator
from .DecoratorHelper import DecoratorHelper
from .CacheDescription import CacheDescription
from .CacheParameters import CacheParameters
from .. import caches


class DecoratorBuilder():
	"""Decorating functions."""

	# Functions to build the decorator nodes.

	try: caches.FIFOCache
	except AttributeError: pass
	else:
		@classmethod
		def fifo_cache(cls, transformer):
			def cachefactory(maxsize = None):
				return CacheDescription(caches.FIFOCache, locals())
			return cls._makenode(transformer, cachefactory)

	try: caches.LFUCache
	except AttributeError: pass
	else:
		@classmethod
		def lfu_cache(cls, transformer):
			def cachefactory(maxsize = None):
				return CacheDescription(caches.LFUCache, locals())
			return cls._makenode(transformer, cachefactory)

	try: caches.LRUCache
	except AttributeError: pass
	else:
		@classmethod
		def lru_cache(cls, transformer):
			def cachefactory(maxsize = None):
				return CacheDescription(caches.LRUCache, locals())
			return cls._makenode(transformer, cachefactory)

	try: caches.MRUCache
	except AttributeError: pass
	else:
		@classmethod
		def mru_cache(cls, transformer):
			def cachefactory(maxsize = None):
				return CacheDescription(caches.MRUCache, locals())
			return cls._makenode(transformer, cachefactory)

	try: caches.RRCache
	except AttributeError: pass
	else:
		@classmethod
		def rr_cache(cls, transformer):
			def cachefactory(maxsize = None, choice = None):
				return CacheDescription(caches.RRCache, locals())
			return cls._makenode(transformer, cachefactory)

	try: caches.TTLCache
	except AttributeError: pass
	else:
		@classmethod
		def ttl_cache(cls, transformer):
			def cachefactory(maxsize = None, ttl = None, timer = None):
				return CacheDescription(caches.TTLCache, locals())
			return cls._makenode(transformer, cachefactory)

	try: caches.TLRUCache
	except AttributeError: pass
	else:
		@classmethod
		def tlru_cache(cls, transformer):
			def cachefactory(maxsize = None, ttu = None, timer = None):
				return CacheDescription(caches.TLRUCache, locals())
			return cls._makenode(transformer, cachefactory)

	try: caches.UnboundedCache
	except AttributeError: pass
	else:
		@classmethod
		def unbounded_cache(cls, transformer):
			def cachefactory():
				return CacheDescription(caches.UnboundedCache)
			return cls._makenode(transformer, cachefactory)

	try: caches.UnboundedTTLCache
	except AttributeError: pass
	else:
		@classmethod
		def unbounded_ttl_cache(cls, transformer):
			def cachefactory(ttl = None, timer = None):
				return CacheDescription(caches.UnboundedTTLCache)
			return cls._makenode(transformer, cachefactory)

	@classmethod
	def _makenode(cls, transformer, cachefactory):
		def node(*args, **kwargs):
			if args and DecoratorHelper.is_callable(args[0]):
				# Called as decorator. Return decorated function.
				cachefactoryparams = CacheParameters.bind(cachefactory, _strict=True)
				cache = cachefactory(**cachefactoryparams)
				decorator = Decorator(cache, _transformer=transformer)
				decorated = decorator(args[0])
				return transformer(decorated)
			else:
				# Called as decorator factory. Return decorator.
				cachefactoryparams = CacheParameters.bind(cachefactory, *args, _strict=True, **kwargs)
				cache = cachefactory(**cachefactoryparams)
				args, kwargs = DecoratorHelper.unbind_parameters(cachefactory, *args, **kwargs)
				decorator = Decorator(cache, *args, _transformer=transformer, **kwargs)
				return lambda func: transformer(decorator(func))
		return node

	@classmethod
	def _defaultnode(cls, transformer):
		def node(*args, **kwargs):
			# Provide compatible version of cachetools 'cached' decorator.
			try:
				cachearg = kwargs['cache']
			except KeyError:
				cachearg = args and args[0]
			if (
				DecoratorHelper.is_cache_instance(cachearg) or
				DecoratorHelper.is_cache_class(cachearg) or
				isinstance(cachearg, (CacheDescription, bool))
			):
				# Called with cache argument. Return decorator.
				decorator = Decorator(*args, _transformer=transformer, **kwargs)
				return lambda func: transformer(decorator(func))
			elif DecoratorHelper.is_standard_cache_class(cachearg):
				# Protection against using standard mutable mappings.
				raise TypeError('Cache type must be converted before used in decorator: %s.' % (not isinstance(cachearg, type) and type(cachearg) or cachearg).__name__)
			else:
				# Called without cache argument. Normal node with default cache.
				def cachefactory(maxsize = None):
					return CacheDescription(DecoratorHelper.get_default_cache_class(), locals())
				return cls._makenode(transformer, cachefactory)(*args, **kwargs)
		return node

	@classmethod
	def shared(cls, transformer):
		def node(*args, **kwargs):
			# Provide compatible version of cachetools 'cachedmethod' decorator.
			try:
				sharedarg = kwargs['shared']
			except KeyError:
				if args:
					sharedarg = args[0]
					args = args[1:]
				else:
					sharedarg = None
			if sharedarg and DecoratorHelper.is_callable(sharedarg):
				# Called with shared cache function argument. Return decorator.
				kwargs['shared'] = sharedarg
				kwargs.pop('cache', None)
				decorator = Decorator(False, *args, _transformer=transformer, **kwargs)
				return lambda func: transformer(decorator(func))
			else:
				# Called without shared cache function argument. Not allowed.
				raise TypeError('Expected callable function to retrieve shared cache%s.' % (sharedarg and (', got %s instead' % (type(sharedarg).__name__,)) or '',))
		return node
