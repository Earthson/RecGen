#!/usr/bin/env python

import sys
import types
from traceback import format_exc

def rec_gen(func, callback=None, err_callback=None):
    '''
    callback: run after func finish
    '''
    def trans_func(*args, **kwargs):
        def error_do(e):
            print('@rec_func_error:', e, file=sys.stderr)
            print('@rec_func_error_strace:', format_exc(), file=sys.stderr)
            if err_callback is not None:
                err_callback()
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
        ans = []
        def go_through(it=None):
            try:
                em = g.send(it)
                if not hasattr(em, 'dojob'):
                    ans.append(em)
                    go_through(None)
                else:
                    em.dojob(callback=go_through, err_callback=partial(error_do, Exception('Child task failed')))
            except StopIteration as st:
                if callback is not None:
                    callback(*ans)
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



if __name__ == '__main__':
    sys.setrecursionlimit(10000000)
    def fib(n):
        if n <= 1:
            yield n
        else:
            yield (yield RecTask(fib, n-1)) + (yield RecTask(fib, n-2))
    pfib = rec_gen(fib, lambda x: print(x))
    for i in range(17):
        pfib(i)
