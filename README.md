RecGen
======

recursive by Generator in Python

Python的generator最常用的方式就是作为迭代器使用，在Python中，可迭代对象是非常的实用。但是generator远比迭代器来得强大，从某版本开始，generator就拥有send方法了，这使得generator具有了在执行过程中接收外部输入的值后继续执行的能力。

当我们持有一个generator之后，我们可以做什么呢？

我们可以获得它的输出，并且给它传值。这里，隐含了一种特殊的模式，generator输出任务，而我们传入任务的执行结果。这个过程看起来就像一次函数调用一样:) 

这里最关键的一点是，我们持有了任务的处理过程，而generator并不关心任务是如何被处理的。实际上，我们可以直接执行，或者丢给异步引擎，或者丢到线程池，或者干脆提交到远程机器上执行。我们把这个分配任务的部分叫做**调度器**吧:)

---

# 递归

如果generator生成的任务本身也是generator呢？我们应当如何让generator完成递归呢？

### 如何返回值？

其实我们直接用yield返回值即可。但是我们需要把任务和值区分开来，因为python并没有提供什么有效的方式能把这两者分离。所以我们通过yield出的值的类型判断即可，我们可以定义一个接口，所有持有某个方法的对象都是任务。

### 调度器的困境

这里有一个重要的问题是，也就是generator的下一次操作，取决于任务是否完成。而这个操作是由任务决定的，调度器无法做到这一点。这导致一个问题，调度器不能直接控制generator的执行，它需要把控制的操作下传给任务，让任务在结束后自动完成这个操作。只有这样，调度器才不需要独立的线程或者额外的方式进行控制，因为它的触发是被动的。

### 执行任务

任务的执行需要接受一个`callback`和一个`error_callback`函数，当任务完成的时候，它执`callback`，出现错误则执行`error_callback`。

我们需要把对于generator的控制封装到一个`callback`中，使得任务可以调用这个函数，完成它的功能。我们可以把重试的函数作为`error_callback`传入任务，这使得任务在失败之后可以被重试。

# 实现

下面是一个实现。包含了如下的一些特性。

 - 调度器可以作为装饰器使用（如果忽略错误和返回值）
 - 对于正常的函数，它能够直接返回结果（传递给callback）
 - 对于普通的generator输出，它能把generator的输出作为参数传递给callback
 - 所有的任务对象都包含一个`dojob`方法，它接受`callback`和`err_callback`，用于完成任务
 - 任务包含了重试机制，当任务失败次数达到限额之后，整个任务会直接失败（整个递归过程）

#### RecTask任务

 - 默认的`RecTask`类型，是常规的python函数调用，包含函数和它的参数。
 - `RecTask`方法包含一个transform方法，用于对任务函数进行变换（完全是一个约定）。这个方法不会修改原始的任务函数，因为一个可变对象在重复调用的过程中会出现难以预计的问题。
 - `RecTask`的`run`方法，用于接受新的任务函数（如果是`None`则直接执行原始的函数）
 - 通过继承`RecTask`，可以构造其它的任务执行方式。比如通过异步引擎来执行任务。这也使得异步架构能够完成一些递归任务:)


奉上一段fibonacci序列的代码。你可以单纯的把`yield RecTask`看成`apply`。这个程序的一个问题是，它对栈空间消耗特别大:)

```python
sys.setrecursionlimit(10000000)

def fib(n):
    if n <= 1:
        yield n
    else:
        yield (yield RecTask(fib, n-1)) + (yield RecTask(fib, n-2))

pfib = rec_gen(fib, lambda x: print(x))
for i in range(15):
    pfib(i)
```
#### 一个典型的异步HTTPTask

我们假定`sender(request, callback)`是一个异步接口。那么我们的异步Task任务如下:)

```python
class HTTPTask(RecTask):
    def __init__(self, sender, req, callback):
        self.sender = sender
        self.req = req
        self.callback = callback

    def transform(self, f):
        return f(self.callback)

    def run(self, callback=None):
        if callback is None:
            callback = self.callback
        self.sender(self.req, callback)


```
