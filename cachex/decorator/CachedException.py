# -*- coding: utf-8 -*-


import traceback, os, re


class NonException(BaseException):
	"""Dummy exception class that does not match any other exception class."""
	pass


class CachedException():
	"""Object to cache when an exception occurs."""

	# To clean exception traceback, specify a list of module files to delete from the top of the traceback.
	# Note: Use always '/' directory separator, if any.
	# Note: Wildcards '*' allowed.
	_clean_traced_modules = ['cached/decorator/*.*']

	def __init__(self, exception):
		self._exception = exception
		self._traceback = exception.__traceback__
		self._clean_traceback()

	def _clean_traceback(self):
		if self._traceback and self._clean_traced_modules:
			# Skip specified modules' frames from the top of the trace.
			tb = self._traceback
			rexp_modules = [s.replace('/', '\\' + os.path.sep).replace('.', '\\.').replace('*', '[\\w]*') for s in self._clean_traced_modules]
			rexp = '(.*\\' + os.path.sep + ')?(' + '|'.join(rexp_modules) + ')$'
			for frame in traceback.extract_tb(tb):
				if re.match(rexp, frame.filename):
					try:
						tb.tb_frame.clear()
					except RuntimeError:
						pass
					tb = tb.tb_next
				else:
					break
			self._traceback = tb

	@property
	def exception(self):
		return self._exception.with_traceback(self._traceback)

	def __repr__(self):
		return '<error %r>' % (self._exception,)
