#!/usr/bin/env python

import sys
import types
from traceback import format_exc

def rec_gen(func, callback=None, err_callback=None):
    '''
    callback accept arguments with output of func
    err_callback is called after Exception occured, accept Exception instance as it's arguments
    '''
    def trans_func(*args, **kwargs):
        def error_do(e):
            print('@rec_func_error:', e, file=sys.stderr)
            if err_callback is not None:
                err_callback(e)
        try:
            g = func(*args, **kwargs)
        except Exception as e:
            error_do(e)
            return
        if not isinstance(g, types.GeneratorType):
            #return if g is not generator
            if callback is not None:
                callback(g)
            return
        #ans = []
        def go_through(it=None):
            try:
                em = g.send(it)
                if not hasattr(em, 'dojob'):
                    #ans.append(em)
                    go_through(None)
                else:
                    em.dojob(callback=go_through, err_callback=error_do)
            except StopIteration as st:
                if callback is not None:
                    callback(st.value)
                return
            except Exception as e:
                g.close()
                error_do(e)
                return
        go_through()
    return trans_func


from functools import partial


class RecTask(object):
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def dojob(self, callback=None, err_callback=None):
        self.run(self.transform(partial(rec_gen, callback=callback, err_callback=err_callback)))

    def transform(self, f):
        return f(self.func)

    def run(self, func=None):
        if func is None:
            func = self.func
        return func(*self.args, **self.kwargs)


class TaskWithRetry(RecTask):

    retry_limit = 1

    def dojob(self, callback=None, err_callback=None):
        try_cnt = 0
        def ierr(e, *args, **kwargs):
            nonlocal try_cnt
            if not hasattr(self, 'retry_limit') or try_cnt > self.retry_limit:
                print('@error: overflow retry limit! task has complete failed', file=sys.stderr)
                if err_callback is not None:
                    return err_callback(e, *args, **kwargs)
                return
            try_cnt += 1
            print('@warning_retry: retry count: %s, %s' % (try_cnt, e), file=sys.stderr)
            self.run(self.transform(partial(rec_gen, callback=callback, err_callback=ierr)))
        self.run(self.transform(partial(rec_gen, callback=callback, err_callback=ierr)))


class MapTask(object):
    def __init__(self, *tasks):
        self.tasks = list(tasks)

    def dojob(self, callback=None, err_callback=None):
        self.ans = [None for e in self.tasks]
        self.flags = [False for e in self.tasks]
        self.cnt = len(self.tasks)
        self.todo = callback
        self.apply_tasks(err_callback=err_callback)

    def apply_tasks(self, err_callback):
        for i, e in zip(range(len(self.tasks)), self.tasks):
            e.dojob(callback=self.acker(i), err_callback=err_callback)

    def acker(self, posi):
        def ack(x):
            if self.flags[posi] is False:
                self.flags[posi] = True
                self.ans[posi] = x
                self.cnt -= 1
            if self.cnt == 0:
                if self.todo is not None:
                    self.todo(tuple(self.ans))
        return ack


class HTTPTask(TaskWithRetry):
    def __init__(self, sender, req, callback):
        self.sender = sender
        self.req = req
        self.callback = callback
        self.retry_limit = 10

    def transform(self, f):
        return f(self.callback)

    def run(self, callback=None):
        if callback is None:
            callback = self.callback
        self.sender(self.req, callback)


if __name__ == '__main__':
    sys.setrecursionlimit(1000000000)
    def fib(n):
        if n <= 1:
            return n
        return (yield RecTask(fib, n-1)) + (yield RecTask(fib, n-2))
        #x, y = yield MapTask(RecTask(fib, n-1), RecTask(fib, n-2))
        #return x + y
    pfib = rec_gen(fib, lambda x: print(x))
    pfib(25)
