<a id="top"></a>
[cachex] decorator
==================

[cachex] provides a decorator intended for memoizing calls to functions, methods and even properties. This can save time when a call is often issued with the same arguments.

- [Basic usage](#basic-usage)
- [Syntax](#syntax)
  - [Cache specification](#cache-specification)
  - [Using transformers](#using-transformers)
  - [Generic parameters](#generic-parameters)
- [Features](#features)
  - [Type dependent caching](#type-dependent-caching)
  - [Error caching](#error-caching)
  - [State dependent caching](#state-dependent-caching)
  - [Per-instance cache](#per-instance-cache)
  - [Shared cache](#shared-cache)
  - [Transformers](#transformers)
  - [Accessors](#accessors)
  - [Defaults management](#defaults-management)
  - [Other features](#other-features)
- [Compatibility](#compatibility)

<br/>

# Basic usage

Here is the simplest possible use.

```python
from cachex import cached

@cached
def myfunction(some_arg, ...):
    ...
    return some_value
```

This will use a default [cache class] to cache the results returned by the function, based on the function parameters. The next time it is called with the same parameter values the function will not be executed again, but instead the result value will be retrieved from the cache.

The cache maximum size can be specified explicitly.

```python
@cached(maxsize=1024)
def myfunction(some_arg, ...):
    ...
    return some_value
```

__Note__: This ```maxsize``` parameter will be used as example throughout this document to illustrate where cache parametes are allowed.

Methods can also be cached.

```python
class MyClass():

    @cached
    def mymethod(self, some_arg, ...):
        ...
        return some_value
```

Even lambda functions can be cached.
```python
cached_function = cached(lambda some_arg: ...)
# or with maximum size...
cached_function = cached(maxsize=1024)(lambda some_arg: ...)
```

<br/>

# Syntax

The generic syntax for the ```@cached``` decorator is as follows.

```python
@cached[.<transformer>][.<cache variant>]([<cache parameters>][, <generic parameters>])
```

Let us go by parts.

<br/>

## Cache specification

The cache to use for memoizing call results can be specified in four ways.

<br/>

- ### By default

  If not specified at all, a [default] cache will be created and used.

  ```python
  from cachex import cached

  @cached(maxsize=1024)
  def myfunction(some_arg, ...):
      ...
      return some_value
  ```

<br/>

- ### Explicitly
  
  Specifying an instance of a [cachex] [cache class].

  ```python
  from cachex import cached, caches

  @cached(caches.UnboundedTTLCache(ttl=3600))
  def myfunction(some_arg, ...):
      ...
      return some_value
  ```

  For convenience, the [main pool](./caches.md#pools-of-cache-classes) of cache classes is included in the decorator, so you do not need to import it.

  ```python
  from cachex import cached

  @cached(cached.caches.UnboundedTTLCache(ttl=3600))
  def myfunction(some_arg, ...):
      ...
      return some_value
  ```

  You can also specify the [cache class] itself, and it will be created using the decorator [defaults].
  
  ```python
  from cachex import cached

  @cached(cached.caches.UnboundedTTLCache)
  def myfunction(some_arg, ...):
      ...
      return some_value
  ```

  Boolean values can also be used, in the sense of "cache values" or "do not cache values".

  ```python
  # This creates and uses a default cache with default configuration.
  @cached(True)
  def myfunction(some_arg, ...):
      ...
      return some_value
  ```

  ```python
  # This uses no caching.
  @cached(False)
  def myfunction(some_arg, ...):
      ...
      return some_value
  ```
  
  __Note__: If you specify ```False```, the decorator will actually create and use a dummy cache, one that does not cache anything and always misses. This is done to keep things consistent internally, and has the same effect as not caching calls at all.

  However this is not exactly the same as calling the bare function, using the decorator adds some overhead to the call, so please use this just for testing purposes.

  If you want to test a cache and compare its performance against not using a cache, you can use the ```uncached``` [accessor](#accessors).

<br/>

- ### Builtin variants

  There are some variants builtin in the decorator to easily use the cache classes already incorporated in [cachex].

  All arguments are optional and can take [default] values. Even the parenthesis are optional.

  - Cache with first-in first-out (FIFO) eviction algorithm (requires cachetools version >= 4.2.0).

    ```python
    @cached.fifo_cache(maxsize)
    ```

  - Cache with least frequently used (LFU) eviction algorithm (requires cachetools version >= 4.0.0).

    ```python
    @cached.lfu_cache(maxsize)
    ```

  - Cache with least recently used (LRU) eviction algorithm (requires cachetools version >= 4.0.0).

    ```python
    @cached.lru_cache(maxsize)
    ```

  - Cache with most recently used (MRU) eviction algorithm (requires cachetools version >= 4.2.0 and < 6.0.0).

    ```python
    @cached.mru_cache(maxsize)
    ```

  - Cache with random replacement eviction algorithm (requires cachetools version >= 4.0.0).

    ```python
    @cached.rr_cache(maxsize, choice)
    ```

  - Cache with least recently used (LRU) eviction algorithm and per-item time-to-live (TTL) (requires cachetools version >= 4.0.0).

    ```python
    @cached.ttl_cache(maxsize, ttl, timer)
    ```

  - Cache with time-aware least recently used (TLRU) eviction algorithm (requires cachetools version >= 5.0.0).

    ```python
    @cached.tlru_cache(maxsize, ttu, timer)
    ```

  - Unbounded cache with no eviction algorithm.

    ```python
    @cached.unbounded_cache()
    ```

  - Unbounded cache with per-item time-to-live (TTL) (requires cachetools version >= 4.0.0).

    ```python
    @cached.unbounded_ttl_cache(ttl, timer)
    ```

  Please refer to the specific [cache implementations](caches.md#cache-implementations) for information about the meaning of the parameters.

<br/>

- ### As shared cache

  Instead of being created by the decorator, the cache instance can also be provided by a function.

  ```python
  @cached.shared(func)
  ```

  For example, by a function that periodically clears the function cache.

  ```python
  import time
  from cachex import cached, caches

  myfunction_cache = caches.UnboundedCache()
  last_time = time.monotonic()

  def periodically_cleared_cache():
       current_time = time.monotonic()
       if current_time - last_time > 3600:
           myfunction_cache.clear()
           last_time = current_time
       return myfunction_cache

  @cached.shared(periodically_cleared_cache)
  def myfunction(some_arg, ...):
      ...
      return some_value
  ```

  This becomes specially powerful when caching object methods, as the passed function can optionally receive the bound object as argument.

  ```python
  class MyClass():

      sharedcache = cached.caches.UnboundedCache()

      @cached.shared(lambda self: self.sharedcache)
      def mymethod(self, some_arg, ...):
          ...
          return some_value
  ```

  Please refer to the section about [shared cache](#shared-cache) for more details and examples.

<br/>

## Using transformers

Cached static methods, class methods and properties can be declared by using transformers.

To declare a cached static method:

```python
class MyClass():

    @cached.staticmethod[...]
    def mystaticmethod(some_arg, ...):
        ...
        return some_value
```

To declare a cached class method:

```python
class MyClass():

    @cached.classmethod[...]
    def myclassmethod(cls, some_arg, ...):
        ...
        return some_value
```

To declare a cached object property:

```python
class MyClass():

    @cached.property[...]
    def myproperty(self):
        ...
        return some_value
```

On top of that you can apply any [cache specification](#cache-specification). So you can use things like these:

```python
@cached.staticmethod(cached.caches.RRCache)
```
```python
@cached.classmethod.shared(lambda cls: cls.sharedcache)
```
```python
@cached.property.ttl_cache(ttl=3600)
```

Please refer to the section about [transformers](#transformers) for details and examples.

<br/>

## Generic parameters

All the decorator variants accept some generic parameters to specify the caching features applied to the specific function/method/property memoization.

- ```typed```

  Allows to distinguish calls to the cached function taking into account the types of the passed arguments and not only its values.

  Values:

  - ```False``` ([default])
  
    Argument types will not be taken into account.

  - ```True```

    Results will be cached taking into account the argument types.

  Refer to the section about [type dependent caching](#type-dependent-caching) for details and examples.

- ```exceptions```

  Allows to cache as valid results of the calls any exception or specific exception types raised by the cached function.

  Values:

  - ```False``` or ```None``` ([default])
  
    No exceptions will be cached.

  - ```True```
   
    All exceptions will be cached.

  - exception class

    Class of exceptions to be cached.

  - (exception class, ...)
  
    Sequence of exception classes to be cached.

  Refer to the section about [error caching](#error-caching) for details and examples.

- ```stateful```

    When caching a method, allows to distinguish calls taking into account the state of the object instance which the method is bound to.

    Values:

    - ```False``` ([default])
    
      Object state will not be taken into account.

    - ```True```
    
      Take into account the object state when caching calls results.

    - callable function

      Take into account the object state as returned by the specified function.

  Refer to the section about [state dependent caching](#state-dependent-caching) for details and examples.

- ```shared```

    When caching a method, determines if the instantiated objects will use a cache shared by all class instances or its own independent clone of the specified cache.

    Values:

    - ```True``` ([default])

      All object instances will share the same cache for the method.

    - ```False```

      Each object instance will use its own specific cache instance for the method.

    - callable function

      The specified function will be used to obtain a cache instance. This use of the parameter is incidental and is not recommended. Use [```@cached.share``` syntax](#as-shared-cache) instead and refer to the section about [shared cache](#shared-cache).

  Refer to the section about [per-instance cache](#per-instance-cache) for details and examples.

- ```key```

  __Note__: This parameter is provided to provide [compatibility](#compatibility) with [cachetools]. Refer to the [cachetools documentation] for details.

  Allows to specify a custom function to convert call parameters into a hashable structure to use it as cache key.

  When specified, this parameter overrides the behaviour specified by the ```typed``` parameter.

  Values:

  - ```None``` ([default])

    The ```typed``` parameter will determine which cache key function will be used.

  - callable function

    Function that receives all arguments passed to a call and returns them into a hashable structure.

- ```lock```

  __Note__: This parameter is provided to provide [compatibility](#compatibility) with [cachetools]. Refer to the [cachetools documentation] for details.

  Allows to specify a custom lock object to override the [integrated cache lock](./caches.md#integrated-locking-capability) used to provide thread-safe access to the cache.

  Values:

  - ```None``` ([default])

    The [integrated cache lock](./caches.md#integrated-locking-capability) will be used.

  - lock object
  
    The specified [lock](https://docs.python.org/library/threading.html#lock-objects) or [semaphore](https://docs.python.org/library/threading.html#semaphore-objects) object will be used.

    Example:

    ```python
    import threading
    from cachex import cached

    @cached(lock=threading.RLock())
    def myfunction(some_arg, ...):
        ...
        return some_value
    ```

  - callable function

    Function that provides the [lock](https://docs.python.org/library/threading.html#lock-objects) or [semaphore](https://docs.python.org/library/threading.html#semaphore-objects) object that will be used.

    When caching a method, if the specified function accepts an argument it will be used as a getter and the bound object will be passed as argument.

    Example:

    ```python
    import threading
    from cachex import cached

    class MyClass():

        mymethod_lock = threading.RLock()

        @cached(lock=operator.attrgetter('mymethod_lock'))
        def mymethod(self, some_arg, ...):
            ...
            return some_value
    ```

    __Note__: The provided lock object must be created only once, not each time the function is called. The provider function will be called an undetermined number of times, so it would be an error to create a lock object each time it is called.

    If the provided function accepts two arguments, the cached function name will be passed too. This allows the custom lock provider to know which method the lock object is for.

<br/>

# Features

The decorator provides multiple features aimed at easing and solving call memoizing needs.

<br/>

## Type dependent caching

The ```typed``` parameter allows to store the call results depending on the parameter types and not only on its values.

Examples:

```python
@cached(typed=False)
de myfunction(some_arg):
    ...
    return some_value

# These calls will be considered the same,
# as ignoring its type the arguments have the same value.
myfunction(3)
myfunction(3.0)
```
```python
@cached(typed=True)
de myfunction(some_arg):
    ...
    return some_value

# These calls will be considered distinct and will be cached separately,
# as the type or the arguments differ despite its values being equivalent.
myfunction(3)
myfunction(3.0)
```

<br/>

## Error caching

When a call results in an error, there may be situations where it is convenient to cache that result too. Time can be saved by not executing the function again just to get the same error.

Using the ```exceptions``` parameter you can set any or specific exceptions to be cached as call results when raised by the cached function. Whenever the function is called again with the same parameters, the cached exception will be raised again.

Examples:

```python
# Any exception raised by the function
# will be cached as a call result.
@cached(exceptions=True)
def myfunction(some_arg, ...):
    ...
    return some_value
```
```python
# Only raised exceptions of the specified type
# will be cached as a call result.
@cached(exceptions=ValueError)
def myfunction(some_arg, ...):
    ...
    return some_value
```
```python
# Only raised exceptions of the specified types
# will be cached as a call result.
@cached(exceptions=(ValueError,TypeError))
def myfunction(some_arg, ...):
    ...
    return some_value
```
```python
# No exceptions will be cached as call results. When the function
# raises and exception that call will not be cached.
@cached(exceptions=False)
def myfunction(some_arg, ...):
    ...
    return some_value
```

<br/>

## State dependent caching

When caching an object method, the ```stateful``` parameter allows to take into account the state of the bound object instance to distinguish method calls.

Consider the next example case.

```python
class Number():
    def __init__(self, value):
        self.value = value

    @cached(stateful=False)
    def sum(self, x):
        return self.value + x
```

Subsequent calls to the method will produce wrong results due to caching.

```python
number = Number(0)
print(number.sum(1))    # -> 1

number.value = 5
print(number.sum(1))    # -> 1, cached value

# The second result is wrong, as the cached value
# does not reflect the current object state.
```

Now let us have into account the object state.

```python
class Number():
    def __init__(self, value):
        self.value = value

    @cached(stateful=True)
    def sum(self, x):
        return self.value + x
```
```python
number = Number(0)
print(number.sum(1))    # -> 1

number.value = 5
print(number.sum(1))    # -> 6, result is calculated again,
                        #       as the object state has changed.
number.value = 0
print(number.sum(1))    # -> 1, value previously cached
                        #       with the same current object state.
```

Setting the ```stateful``` parameter to ```True``` makes the decorator use the object state as part of the cache key, along with the function parameters. So calls with the same parameters but different object state will be considered as different calls.

The object state is obtained using the next process.
- First the [```object.__getstate__()```](https://docs.python.org/library/pickle.html#object.__getstate__) method is tried if present.
- If that method is not present, the instance ```__dict__``` will be used as object state.
- If object instance has no ```__dict__```, then the state will be composed by the properties declared as object ```__slots__```, if present.
- If everything else fails, the object hash will be used as object state.

The ```stateful``` parameter also allows to specify a custom function to provide just the object state properties that are relevant for the specific cached method. The custom state returned can either be a scalar or a collection (sequence, mapping, ...).

So in the previous example this could be used.

```python
class Number():
    def __init__(self, value):
        self.value = value

    @cached(stateful=lambda self: self.value)
    def sum(self, x):
        return self.value + x
```

<br/>

## Per-instance cache

When caching an object method, the ```shared``` parameter allows to specify whether the method will use a cache shared by all the class instances or an independent cache for each instantiated object.

Example of method using a class shared cache.

```python
class MyClass():

    @cached(shared=True)
    def mymethod(self, some_arg):
        ...
        return some_value

instance1 = MyClass()
instance2 = MyClass()

# All class instances share the same method cache.
assert(instance1.mymethod.cache == instance2.mymethod.cache)

instance1.mymethod("a")    # Cache a pair of results.
instance1.mymethod("b")    # using one specific instance.

# Results cached for all instances.
assert(instance1.mymethod.cache.currsize == 2)
assert(instance2.mymethod.cache.currsize == 2)
```

Example of method using per-instance independent cache.

```python
class MyClass():

    @cached(shared=False)
    def mymethod(self, some_arg):
        ...
        return some_value

instance1 = MyClass()
instance2 = MyClass()

# Each instance uses its own independent cache.
assert(instance1.mymethod.cache != instance2.mymethod.cache)

instance1.mymethod("a")    # Cache a pair of results.
instance1.mymethod("b")    # using one specific instance.

# Results cached only in that instance.
assert(instance1.mymethod.cache.currsize == 2)
assert(instance2.mymethod.cache.currsize == 0)
```

<br/>

## Shared cache

The ```shared``` parameter can also specify a function that provides the cache to be used by the method. Of course then the [cache specified](#cache-specification) in the decorator looses its sense, so the prefered way to use this feature is to use the [```@cached.shared``` syntax](#as-shared-cache).

Example of shared class cache using this feature.

```python
class MyClass():

    # Cache shared by all instances.
    mymethod_shared_cache = cached.caches.Cache()

    @cached.shared(operator.attrgetter('mymethod_shared_cache'))
    def mymethod(self, some_arg, ...):
        ...
        return some_value
```

Example of per-instance cache using this feature.

```python
class MyClass():

    def __init__(self):
        # Create one cache for each instance.
        self.mymethod_instance_cache = cached.caches.Cache()

    @cached.shared(operator.attrgetter('mymethod_instance_cache'))
    def mymethod(self, some_arg, ...):
        ...
        return some_value
```

This allows the object class to do more powerful cache management for the method.

Example: method using different cache type depending on the object instance characterization.

```python
class MyClass():

    def __init__(self, use_cache):
        self.use_cache = use_cache

    def mymethod_cache_getter(self):
        try:
            return self.mymethod_cache
        except AttributeError:
            # If not created, create cache instance
            # depending on object characterization.
            if self.use_cache:
                self.mymethod_cache = cached.caches.Cache()
            else:
                self.mymethod_cache = cached.caches.NoCache()
        return self.mymethod_cache

    @cached.shared(operator.methodcaller('mymethod_cache_getter'))
    def mymethod(self, some_arg, ...):
        ...
        return some_value


# This instance will use cache for the method 'mymethod'.
instance1 = MyClass(use_cache=True)

# This instance will use no caching for the method 'mymethod'.
instance2 = MyClass(use_cache=False)
```

__Note__: Please note that the provided cache must be created only once, not each time the cache getter is called. The cache getter will be called an undetermined number of times, so it would be an error to create a cache instance each time it is called.

If the cache getter accepts two arguments, the cached function name will be passed as second argument. This allows to setup a specialized method to provide caches for all methods in an object.

Example: methods using different cache type depending on the object instance characterization.

```python
class MyClass():

    def __init__(self, use_cache):
        self.use_cache = use_cache

    def caches_provider(self, method_name):
        try:
            return self.caches[method_name]
        except AttributeError:
            # On first call, setup container for methods´ caches.
            self.caches = {}
            return self.caches_provider(method_name)
        except KeyError:
            # If not created, create cache instance
            # for the specific method
            # depending on object characterization.
            if self.use_cache:
                self.caches[method_name] = cached.caches.Cache()
            else:
                self.caches[method_name] = cached.caches.NoCache()
        return self.caches[method_name]

    @cached.shared(caches_provider)
    def mymethod(self, some_arg, ...):
        ...
        return some_value

    @cached.shared(caches_provider)
    def othermethod(self, some_arg, ...):
        ...
        return some_value
```

<br/>

## Transformers

Trying to cache static methods, class methods or properties as if they were functions may not work as intended.

```python
# This will not work.
class MyClass():

    @cached
    @property
    def myproperty(self):
        ...
        return some_value
```

Instead, the ```@cached``` decorator allows to directly declare them as cached.

```python
# This will work.
class MyClass():

    @cached.property
    def myproperty(self):
        ...
        return some_value
```

Four transformers are provided for this purpose.

- Cached static method
 
  ```@cached.staticmethod```

- Cached class method
 
  ```@cached.classmethod```

- Cached object property
 
  ```@cached.property```

- Cached function
 
  ```@cached.function```

  __Note__: Using the ```function``` transformer is equivalent to not using a transformer at all, and it is provided only for coherence.

Examples:

```python
import operator
from cachex import cached

class MyClass():

    sharedcache = cached.caches.UnboundedCache()

    # This declares a cached class method.
    @cached.classmethod.shared(operator.attrgetter('sharedcache'))
    def myclassmethod(cls, some_arg, ...):
        ...
        return some_value

    # This declares a cached static method.
    @cached.staticmethod(cached.caches.RRCache(maxsize=1024))
    def mystaticmethod(some_arg, ...):
        ...
        return some_value

    # This declares a cached property.
    @cached.property.ttl_cache(ttl=3600, stateful=True)
    def myproperty(self):
        ...
        return some_value
```

<br/>

## Accessors

When a function or method is cached, the decorated function is instrumented with some convenience callable attributes that allow to access, check and manage the used cache, and also to test the caching performance.

Given a cached function or method...

```python
@cached[...]
def myfunction(some_arg, ...):
    ...
    return some_value
```

... the next accessors are provided,

- myfunction```.uncached(some_arg, ...)```

  Allows to call the original uncached version of the cached function or method.

- myfunction```.cache```\
  myfunction```._cache()```

  Allows to access the cache instance being used to memoize the function or method calls.

- myfunction```.cache_lock```\
  myfunction```._cache_lock()```

  Returns the lock being used to access the cache.

- myfunction```.cache_key```
 
  Returns the key function used to access the cache items.

- myfunction```.cache_clear()```

  Clears or invalidates the cache being used.

- myfunction```.cache_info()```

  Returns a named tuple showing the cache hits, misses, maximum size and current size. This helps measuring the efectiveness of the cache and helps tuning its parameters.

- myfunction```.cache_parameters()```

  Returns a new dictionary showing the value for ```typed``` parameter along with the parameters used to create the cache. This is for information purposes only. Mutating the values has no effect.

- myfunction```.cache_configuration()```

  Returns a new dictionary showing all the relevant parameters used for the cache setup. This is for information purposes only. Mutating the values has no effect.

These accessors will always point to the right cache instance used for the referenced function or method they are attached to, no matter if caching functions or methods, if using a shared cache or per-instance cache, or whatever cache specification is used in the decorator.

For example:

```python
# Let us cache a method using per-instance independent caches.
class MyClass():

    @cached(cached.caches.Cache(), shared=False)
    def mymethod(self, some_arg, ...):
        ...
        return some_value

instance = MyClass()

# This points to the cache specified in the decorator,
# actually unused as each bound method uses a clone of it.
MyClass.mymethod.cache

# And this points to the independent cache
# used by the specific instance.
instance.mymethod.cache

# The cache used by a specific instance can also be accessed
# with an unbound call.
MyClass.mymethod._cache(instance)
```

This coherence is also valid for the ```uncached``` accessor.

```python
# This does not only point to the uncached variant of the method,
# but to the uncached variant bound to the specific instance.
instance.mymethod.uncached(some_arg, ...)

# Unbound calls can also be used, as with any method.
MyClass.mymethod.uncached(instance, some_arg, ...)
```

Accessors can also be used to access or invalidate individual cache items.

```python
@cached
def myfunction(some_arg, ...):
    ...
    return some_value

# Always use the cache key function accessor for accessing cache items.
with myfunction.cache_lock:
    key = myfunction.cache_key(42)
    old_value = myfunction.cache.pop(key, None)
    myfunction.cache[key] = new_value
```

When the ```stateful``` parameter feature is used, the resulting key function takes into account the object state as part of the cache key. So using the original key function to access cache items will not work. The ```cache_key``` accessor must always be used to obtain cache keys from function arguments.

```python
def keyfunc(some_arg, ...):
    return hash(some_arg)

class MyClass():

    @cached(key=keyfunc, stateful=True)
    def mymethod(self, some_arg, ...):
        ...
        return some_value

    @cached.classmethod(key=keyfunc, stateful=True)
    def myclassmethod(cls, some_arg, ...):
        ...
        return some_value

instance = MyClass()

with instance.mymethod.cache_lock:
    # This will not work.
    #key = keyfunc(42)
    # This will work.
    key = instance.mymethod.cache_key(42)
    ...
    old_value = instance.mymethod.cache.pop(key, None)
    instance.mymethod.cache[key] = new_value

with MyClass.myclassmethod.cache_lock:
    # This will not work.
    #key = keyfunc(42)
    # This will work.
    key = MyClass.myclassmethod.cache_key(MyClass, 42)
    ...
    old_value = MyClass.myclassmethod.cache.pop(key, None)
    MyClass.myclassmethod.cache[key] = new_value
```

<br/>

## Defaults management

Default parameters for the decorator can be easily accessed and modified, in a similar way that [caches defaults] are managed. Please refer to that part of the documentation for an overview on how to manage parameters defaults.

```python
>>> from cachex import cached
>>> 
>>> cached.defaults
CacheDefaults({'typed': False, 'exceptions': None, 'stateful': False, 'shared': True, 'maxsize': 128, 'maxsize__None': inf, 'ttl': 600, 'ttl__None': inf})
>>> 
>>> cached.defaults.typed
False
>>> cached.defaults.typed = True
```

__Note__: The decorator defaults are applied to decorator parameters only. If you instantiate a cache to pass it to the decorator, on instantiation the [caches defaults] will be applied and not the decorator ones.

Anyway, some of the decorator defaults are dynamically inherited from the [caches defaults], specifically the ones that apply to parameters that correspond to cache instance creation.

```python
>>> from cachex import cached, caches
>>> 
>>> caches.defaults.maxsize         # Default at cache classes level.
128
>>> cached.defaults.maxsize         # Inherited at decorator level.
128
>>> caches.defaults.maxsize = 1024  # Modify at cache classes level.
>>> cached.defaults.maxsize         # Change is inherited at decorator level.
1024
```

However they can be overriden at the decorator level.

```python
>>> cached.defaults.maxsize = 2048  # Override at decorator level.
>>> cached.defaults.maxsize         # Modified at decorator level...
2048
>>> caches.defaults.maxsize         # ... while unchanged at cache classes level.
1024
```

This should be taken into account when deleting modified defaults.

```python
>>> del cached.defaults.maxsize     # Modification deleted at decorator level...
>>> cached.defaults.maxsize         # ... so it inherits again from cache classes level.
1024
```

There are some protected defaults at decorator level. Protected defaults are not shown when defaults are listed but can be modified anyway. Modify them only if you know what you are doing.

```python
# Default cache class.
cached.defaults._cache_class

# Object attribute used to store per-instance caches.
cached.defaults._attr_cache

# List of argument names used to identify unbound methods.
cached.defaults._arg_self
```

<br/>

## Other features

Some other decorator features not so relevant as to be on the big list.

- ### Thread-safe access to cache

  Access to the cache is made thread-safe by default, using either the mutex object provided in the ```lock``` parameter or the [integrated cache lock](./caches.md#integrated-locking-capability).

  __Note__: Only access to the cache is made thread-safe. The decorated function is called outside the mutex context and should be thread-safe by itself.

- ### Mutable-type arguments

  The arguments of the cached function are used as a hash key to store and access memoized results in the cache. This means the arguments should be hashable. However arguments of some non-hashable types are also accepted, like mutable mappings (as ```dict```) or mutable sequences (as ```list```).

  __Note__: This adds a small overhead when composing cache keys from function arguments, so please take it into account when caching functions that use very complex or heavily nested structures as arguments.

- ### Dynamic decoration and reusability

  Not only functions, but also bound methods of specific instances or classes can be dynamically decorated.

  ```python
  import inspect
  from cachex import cached

  class MyClass():

      def mymethod(self, some_arg, ...):
          ...
          return some_value

  instance1 = MyClass()
  instance2 = MyClass()

  # Only this instance method will be memoized.
  instance1.mymethod = cached.lru_cache(instance1.mymethod)

  instance1.mymethod(some_arg, ...)    # This call is cached.
  instance2.mymethod(some_arg, ...)    # This call is not cached.

  # The type and characterization of the decorated method
  # is preserved. Even for the 'uncached' accessor.
  assert(inspect.ismethod(instance1.mymethod))
  assert(inspect.ismethod(instance1.mymethod.uncached))
  ```

  A decorator can be reused to dynamically cache several functions or methods.

  ```python
  from cachex import cached

  def myfunction1(some_arg, ...):
      ...
      return some_value

  def myfunction2(some_arg, ...):
      ...
      return some_value

  decorate = cached.unbounded_cache(ttl=3600)

  myfunction1 = decorate(myfunction1)
  myfunction2 = decorate(myfunction2)
  ```

  The decorator preserves cache independence when reused. This means that, if the cache instance is created internally by the decorator, then each function cached will use its own differentiated cache instance. Otherwise, if the cache instance is created externally to the decorator (by specifying a [cache instance](#explicitly) or a [shared cache](#as-shared-cache)), that instance will be used for all functions cached with the reused decorator.

  Examples:

  With these reusable decorators each decorated function will use its own cache instance, as they are created dynamically by the decorator.

  ```python
  decorate = cached(cached.caches.Cache)
  # or
  decorate = cached(maxsize=1024)
  # or
  decorate = cached.ttl_cache(ttl=3600)
  ```

  With these reusable decorators all decorated functions will use the specified cache instance, because it is not created by the decorator.

  ```python
  decorate = cached(cached.caches.Cache())
  # or
  decorate = cached.shared(cache_getter_function)
  ```

<br/>

# Compatibility

The decorator makes its best to be compatible with other memoizing solutions like [cachetools] or Python [functools] decorators.

- Equivalences

  These are some equivalences between using other memoizing solutions and using the [cachex] decorator.

  - ```python
    @functools.lru_cache[(maxsize, typed)]

    @cachetools.func.fifo_cache[(maxsize, typed)]
    @cachetools.func.lfu_cache[(maxsize, typed)]
    @cachetools.func.lru_cache[(maxsize, typed)]
    @cachetools.func.rr_cache[(maxsize, choice, typed)]
    @cachetools.func.ttl_cache[(maxsize, ttl, timer, typed)]
    @cachetools.func.tlru_cache[(maxsize, ttu, timer, typed)]
    ```

    Using the [cachex] decorator:

    ```python
    @cached.fifo_cache[(maxsize, typed)]
    @cached.lfu_cache[(maxsize, typed)]
    @cached.lru_cache[(maxsize, typed)]
    @cached.rr_cache[(maxsize, choice, typed)]
    @cached.ttl_cache[(maxsize, ttl, timer, typed)]
    @cached.tlru_cache[(maxsize, ttu, timer, typed)]
    ```

    Default parameters values are also compatible, altough they can be modified using [defaults] management.

  - ```python
    @functools.cache
    ```

    Using the [cachex] decorator:

    ```python
    @cached(maxsize=None)
    ```

  - ```python
    @functools.cached_property
    ```

    Using the [cachex] decorator:

    ```python
    @cached.property
    ```

  - ```python
    @cachetools.cached(cache_obj, key=key_func, lock=lock_obj)
    ```

    Using the [cachex] decorator:

    ```python
    @cached(cache_obj, key=key_func, lock=lock_obj)
    ```

  - ```python
    @cachetools.cachedmethod(cache_getter, key=key_func, lock=lock_getter)
    ```

    Using the [cachex] decorator:

    ```python
    @cached.shared(cache_getter, key=key_func, lock=lock_getter)
    ```

- Accessors

  The [cachex] decorator also provides the cache [accesors](#accessors) provided by the [functools] and [cachetools] decorators.

  - cached_function```.cache_info()```
  - cached_function```.cache_clear()```
  - cached_function```.cache_parameters()```

[default]: #defaults-management
[defaults]: #defaults-management
[caches defaults]: ./caches.md#defaults-management
[cachex]: ./README.md#top
[cache class]: ./caches.md#top
[functools]: https://docs.python.org/library/functools.html
[cachetools]: https://github.com/tkem/cachetools/
[cachetools documentation]: https://cachetools.readthedocs.io/en/stable/#memoizing-decorators
