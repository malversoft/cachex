# -*- coding: utf-8 -*-


import uuid, threading, math
from collections import namedtuple

from .CacheParameters import CacheParameters


# CacheInfo implementation.
_CacheInfo = namedtuple('CacheInfo', [
    'hits', 'misses', 'maxsize', 'currsize'
])


# Dummy lock context manager.
class NoLock():
	def __enter__(self):
		return self
	def __exit__(self, exc_type, exc_value, exc_tb):
		return False
	def __bool__(self):
		# Evaluate to False.
		return False


# Context manager to activate or deactivate automatic cache hit/miss counters.
class CountersContext():
	def __init__(self, cache):
		self.__cache = cache
		self.__enable = True
	def __call__(self, enable = True):
		# Allow to enter context specifying state argument.
		self.__enable = enable
		return self
	def __enter__(self):
		# Save counters state.
		self.__counters_enabled = self.__cache.counters_enabled
		# Enable counters.
		self.__cache.counters_enabled = self.__enable
		return self
	def __exit__(self, exc_type, exc_value, exc_tb):
		# Restore counters state.
		self.__cache.counters_enabled = self.__counters_enabled
		self.__enable = True
		return False

	def __bool__(self):
		# Inform if counters are active or used.
		return self.__cache.counters_enabled or self.__cache._counters_used

	def reset(self):
		self.__cache.counters_reset()

	@property
	def enabled(self):
		return self.__cache.counters_enabled
	@enabled.setter
	def enabled(self, value):
		self.__cache.counters_enabled = value


class CacheMixin():

	def __init__(self, *args, **kwargs):

		# Normalize parameters with defaults if needed.
		# WARNING: For this to work well the wrapped cache class must have all its required parameters declared in the constructor.

		# - self.__configuration is a full parameters copy used for cloning purposes.
		self.__configuration = CacheParameters.bind(super().__init__, *args, **kwargs)
		# - self.__parameters has information purposes and can be modified/beautified.
		self.__parameters = self.__configuration.copy()

		# Instantiate cache.
		super().__init__(**self.__configuration)

		if 'getsizeof' in self.__parameters:
			del self.__parameters['getsizeof']
		# The instantiated cache may impose a specific maxsize (for example an unbounded cache)
		# or it may not have maxsize info at all. So update parameters info.
		if 'maxsize' in self.__parameters:
			try:
				self.__parameters['maxsize'] = super().maxsize
			except AttributeError:
				pass
			if self.__parameters['maxsize'] == math.inf:
				self.__parameters['maxsize'] = None

		# Initialize lock.
		self.lock = True

		# Initialize counters.
		self.counters_reset()

		# Initialize automatic counters mechanism.
		self.__counters = CountersContext(self)
		self.__counters_enabled = False
		self.__missed = None
		self.__counters_hits_suspended = self.__counters_misses_suspended = False

		# Initialize hash.
		self.__hash = uuid.uuid4().int

	def _maxsize_info(self):
		if 'maxsize' in self.__parameters:
			return self.__parameters['maxsize']
		else:
			# Cache may not have maxsize parameter. Try to get from parent.
			try:
				maxsize = super().maxsize
			except AttributeError:
				# Support any mutable mapping.
				maxsize = None
			return None if maxsize == math.inf else maxsize

	def _currsize_info(self):
		try:
			return super().currsize
		except AttributeError:
			# Support any mutable mapping.
			return len(self)

	def clone(self):
		# TODO: Clone or copy integrated lock object too?
		return type(self)(**self.__configuration)

	def __hash__(self):
		return self.__hash

	def __repr__(self):
		with self.counters(False):
			items = repr(getattr(self, '_Cache__data', list(self.items())))
		counters = self.counters and ', hits=%r, misses=%r' % (self.__hits, self.__misses,) or ''
		params = ', '.join([
			'%s=%s' % (k, repr(self.__parameters[k]) if not callable(self.__parameters[k]) else str(self.__parameters[k].__name__))
			for k in self.__parameters
			if k not in ('maxsize',)
		])
		return '%s(%s%s, currsize=%r, maxsize=%r%s)' % (
			type(self).__name__,
			items,
			counters,
			self._currsize_info(),
			self._maxsize_info(),
			params and (', %s' % (params,)),
		)

	def __getitem__(self, key):
		if self.__counters_enabled and not self.__counters_hits_suspended:
			self.__counters_hits_suspended = True	# Allow internal recurrent access without triggering ghost hits.
			self.__missed = False
			try:
				v = super().__getitem__(key)
			except KeyError:
				# Support any mutable mapping.
				self.__missed = True
				raise
			finally:
				if self.__missed is False:
					self.did_hit()
				else:
					self.did_miss()
				self.__missed = None
				self.__counters_hits_suspended = self.__counters_misses_suspended = False
			return v
		else:
			return super().__getitem__(key)

	def __missing__(self, key):
		if self.__counters_enabled and not self.__counters_misses_suspended:
			self.__counters_misses_suspended = True	# Allow internal recurrent access without triggering ghost misses.
			self.__missed = True
		try:
			call_missing = super().__missing__
		except AttributeError:
			# Support any mutable mapping.
			raise KeyError(key)
		return call_missing(key)

	def clear(self):
		super().clear()
		# Clear counters too.
		self.counters_reset()

	def counters_reset(self):
		self.__hits = self.__misses = 0
		self.__counters_used = False

	def did_hit(self, increment = 1):
		self.__hits += increment
		self.__counters_used = True

	def did_miss(self, increment = 1):
		self.__misses += increment
		self.__counters_used = True

	@property
	def hits(self):
		return self.__hits

	@property
	def misses(self):
		return self.__misses

	@property
	def counters_enabled(self):
		return self.__counters_enabled

	@counters_enabled.setter
	def counters_enabled(self, value):
		self.__counters_enabled = bool(value)

	@property
	def counters(self):
		return self.__counters

	@property
	def _counters_used(self):
		return self.__counters_used

	@property
	def info(self):
		return _CacheInfo(self.__hits, self.__misses, self._maxsize_info(), self._currsize_info())

	@property
	def lock(self):
		return self.__lock

	# Allow to change lock object. If set to None no lock will be used.
	# Any lock or semaphore can be used, and even shared with another cache instances.
	@lock.setter
	def lock(self, value):
		if not value:
			# Set no lock.
			self.__lock = NoLock()
		elif not hasattr(value, '__enter__') or not hasattr(value, '__exit__'):
			# Set default lock.
			lock_class = self.__configuration._defaults._lock_class
			try:
				self.__lock = lock_class()
			except TypeError:
				# Protection against default changed to a scalar boolean.
				if lock_class:
					self.__lock = threading.RLock()
				else:
					self.__lock = NoLock()
		else:
			# Set specified lock.
			self.__lock = value

	@property
	def parameters(self):
		return dict(self.__parameters)

	@property
	def configuration(self):
		return self.__configuration.copy()
