# -*- coding: utf-8 -*-


# Cache configuration defaults.

class AbstractCacheDefaults():
	"""Caches defaults access."""

	# Defaults prefix.
	_prefix = 'def__'
	_suffix_None = '__None'

	# Property access will affect all created instances by accessing/modifying the class static properties.

	def hasdefault(self, key):
		# Will check only own class defaults.
		return type(self)._prefix + str(key) in type(self).__dict__

	def __getattr__(self, key):
		# Will provide own class and parent classes defaults.
		for kls in type(self).__mro__:
			try:
				prefix = kls._prefix
			except AttributeError:
				break
			try:
				return getattr(type(self), kls._prefix + str(key))
			except AttributeError:
				pass
		raise AttributeError("No default set for '%s'." % key)

	def __setattr__(self, key, value):
		# Will modify only own class defaults.
		setattr(type(self), type(self)._prefix + str(key), value)

	def __delattr__(self, key):
		# Will modify only own class defaults.
		try:
			delattr(type(self), type(self)._prefix + str(key))
		except AttributeError:
			raise AttributeError("No default set for '%s'." % key)

	# Allow to iterate and map.

	def __iter__(self):
		return iter(self.keys())

	def __getitem__(self, key):
		try:
			return getattr(self, key)
		except AttributeError as e:
			raise KeyError(e)

	def __setitem__(self, key, value):
		try:
			return setattr(self, key, value)
		except AttributeError as e:
			raise KeyError(e)

	def __delitem__(self, key):
		try:
			return delattr(self, key)
		except AttributeError as e:
			raise KeyError(e)

	def keys(self):
		keys = []
		for kls in type(self).__mro__:
			try:
				prefix = kls._prefix
			except AttributeError:
				break
			for k in kls.__dict__:
				if k.startswith(prefix):
					key = k[len(prefix):]
					if not key.startswith('_'):		# Hide protected attributes.
						keys.append(key)
		return keys

	def __repr__(self):
		return '%s(%r)' % (type(self).__name__, dict(self))
