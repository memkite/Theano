import copy

import numpy

from type import TypedListType
import theano
from theano.gof import Apply, Constant, Op, Variable
from theano.tensor.type_other import SliceType
from theano import tensor as T
from theano.compile.debugmode import _lessbroken_deepcopy


class _typed_list_py_operators:

    def __getitem__(self, index):
        return getitem(self, index)

    def __len__(self):
        return length(self)

    def append(self, toAppend):
        return append(self, toAppend)

    def extend(self, toAppend):
        return extend(self, toAppend)

    def insert(self, index, toInsert):
        return insert(self, index, toInsert)

    def remove(self, toRemove):
        return remove(self, toRemove)

    def reverse(self):
        return reverse(self)

    def count(self, elem):
        return count(self, elem)

    # name "index" is already used by an attribute
    def ind(self, elem):
        return index_(self, elem)

    ttype = property(lambda self: self.type.ttype)


class TypedListVariable(_typed_list_py_operators, Variable):
    """
    Subclass to add the typed list operators to the basic `Variable` class.
    """

TypedListType.Variable = TypedListVariable


class GetItem(Op):
    # See doc in instance of this Op or function after this class definition.
    view_map = {0: [0]}

    def __eq__(self, other):
        return type(self) == type(other)

    def __hash__(self):
        return hash(type(self))

    def make_node(self, x, index):
        assert isinstance(x.type, TypedListType)
        if not isinstance(index, Variable):
            if isinstance(index, slice):
                index = Constant(SliceType(), index)
                return Apply(self, [x, index], [x.type()])
            else:
                index = T.constant(index, ndim=0, dtype='int64')
                return Apply(self, [x, index], [x.ttype()])
        if isinstance(index.type, SliceType):
            return Apply(self, [x, index], [x.type()])
        elif isinstance(index, T.TensorVariable) and index.ndim == 0:
            assert index.dtype == 'int64'
            return Apply(self, [x, index], [x.ttype()])
        else:
            raise TypeError('Expected scalar or slice as index.')

    def perform(self, node, (x, index), (out, )):
        if not isinstance(index, slice):
            index = int(index)
        out[0] = x[index]

    def __str__(self):
        return self.__class__.__name__

    def c_code(self, node, name, inp, out, sub):
        x_name, index = inp[0], inp[1]
        output_name = out[0]
        fail = sub['fail']
        return """
        %(output_name)s = (typeof %(output_name)s) PyList_GetItem( (PyObject*) %(x_name)s, *((npy_int64 *) PyArray_DATA(%(index)s)));
        if(%(output_name)s == NULL){
            %(fail)s
        }
        Py_INCREF(%(output_name)s);
        """ % locals()

    def c_code_cache_version(self):
        return (1,)

getitem = GetItem()
"""
Get specified slice of a typed list.

:param x: typed list.
:param index: the index of the value to return from `x`.
"""


class Append(Op):
    # See doc in instance of this Op after the class definition.
    def __init__(self, inplace=False):
        self.inplace = inplace
        if self.inplace:
            self.destroy_map = {0: [0]}
            # TODO: make destroy_handler support having views and
            # destroyed version of multiple inputs.
            # self.view_map = {0: [1]}
        else:
            # TODO: make destroy_handler support multiple view
            # self.view_map = {0: [0, 1]}
            self.view_map = {0: [0]}

    def __eq__(self, other):
        return type(self) == type(other) and self.inplace == other.inplace

    def __hash__(self):
        return hash(type(self)) ^ hash(self.inplace)

    def make_node(self, x, toAppend):
        assert isinstance(x.type, TypedListType)
        assert x.ttype == toAppend.type
        return Apply(self, [x, toAppend], [x.type()])

    def perform(self, node, (x, toAppend), (out, )):
        if not self.inplace:
            out[0] = list(x)
        else:
            out[0] = x
        # need to copy toAppend due to destroy_handler limitation
        toAppend = _lessbroken_deepcopy(toAppend)
        out[0].append(toAppend)

    def __str__(self):
        return self.__class__.__name__

    # DISABLED AS WE NEED TO UPDATE IT TO COPY toAppend().
    def _c_code_(self, node, name, inp, out, sub):
        x_name, toAppend = inp[0], inp[1]
        output_name = out[0]
        fail = sub['fail']
        if not self.inplace:
            init = """
            %(output_name)s = (PyListObject*) PyList_GetSlice((PyObject*) %(x_name)s, 0, PyList_GET_SIZE((PyObject*) %(x_name)s)) ;
            """ % locals()
        else:
            init = """
            %(output_name)s =  %(x_name)s;
            """ % locals()
        return init + """
        if(%(output_name)s==NULL){
                %(fail)s
        };
        if(PyList_Append( (PyObject*) %(output_name)s,(PyObject*) %(toAppend)s)){
            %(fail)s
        };
        Py_INCREF(%(output_name)s);
        """ % locals()

    def c_code_cache_version(self):
        return (1,)

append = Append()
"""
Append an element at the end of another list.

:param x: the base typed list.
:param y: the element to append to `x`.
"""


class Extend(Op):
    # See doc in instance of this Op after the class definition.
    def __init__(self, inplace=False):
        self.inplace = inplace
        if self.inplace:
            self.destroy_map = {0: [0]}
            # TODO: make destroy_handler support having views and
            # destroyed version of multiple inputs.
            # self.view_map = {0: [1]}
        else:
            # TODO: make destroy_handler support multiple view
            # self.view_map = {0: [0, 1]}
            self.view_map = {0: [0]}

    def __eq__(self, other):
        return type(self) == type(other) and self.inplace == other.inplace

    def __hash__(self):
        return hash(type(self)) ^ hash(self.inplace)

    def make_node(self, x, toAppend):
        assert isinstance(x.type, TypedListType)
        assert x.type == toAppend.type
        return Apply(self, [x, toAppend], [x.type()])

    def perform(self, node, (x, toAppend), (out, )):
        if not self.inplace:
            out[0] = list(x)
        else:
            out[0] = x
        # need to copy toAppend due to destroy_handler limitation
        if toAppend:
            o = out[0]
            for i in toAppend:
                o.append(_lessbroken_deepcopy(i))

    def __str__(self):
        return self.__class__.__name__

    # DISABLED AS WE NEED TO UPDATE IT TO COPY toAppend().
    def _c_code_(self, node, name, inp, out, sub):
        x_name, toAppend = inp[0], inp[1]
        output_name = out[0]
        fail = sub['fail']
        if not self.inplace:
            init = """
            %(output_name)s = (PyListObject*) PyList_GetSlice((PyObject*) %(x_name)s, 0, PyList_GET_SIZE((PyObject*) %(x_name)s)) ;
            """ % locals()
        else:
            init = """
            %(output_name)s =  %(x_name)s;
            """ % locals()
        return init + """
        int i =0;
        int length = PyList_GET_SIZE((PyObject*) %(toAppend)s);
        if(%(output_name)s==NULL){
                %(fail)s
        };
        for(i; i < length; i++){
            if(PyList_Append( (PyObject*) %(output_name)s,(PyObject*) PyList_GetItem((PyObject*) %(toAppend)s,i))==-1){
                %(fail)s
            };
        }
        Py_INCREF(%(output_name)s);
        """ % locals()

    def c_code_cache_version_(self):
        return (1,)

extend = Extend()
"""
Append all elements of a list at the end of another list.

:param x: The typed list to extend.
:param toAppend: The typed list that will be added at the end of `x`.
"""


class Insert(Op):
    # See doc in instance of this Op after the class definition.
    def __init__(self, inplace=False):
        self.inplace = inplace
        if self.inplace:
            self.destroy_map = {0: [0]}
            # TODO: make destroy_handler support having views and
            # destroyed version of multiple inputs.
            # self.view_map = {0: [2]}
        else:
            # TODO: make destroy_handler support multiple view
            # self.view_map = {0: [0, 2]}
            self.view_map = {0: [0]}

    def __eq__(self, other):
        return type(self) == type(other) and self.inplace == other.inplace

    def __hash__(self):
        return hash(type(self)) ^ hash(self.inplace)

    def make_node(self, x, index, toInsert):
        assert isinstance(x.type, TypedListType)
        assert x.ttype == toInsert.type
        if not isinstance(index, Variable):
            index = T.constant(index, ndim=0, dtype='int64')
        else:
            assert index.dtype == 'int64'
            assert isinstance(index, T.TensorVariable) and index.ndim == 0
        return Apply(self, [x, index, toInsert], [x.type()])

    def perform(self, node, (x, index, toInsert), (out, )):
        if not self.inplace:
            out[0] = list(x)
        else:
            out[0] = x
        # need to copy toAppend due to destroy_handler limitation
        toInsert = _lessbroken_deepcopy(toInsert)
        out[0].insert(index, toInsert)

    def __str__(self):
        return self.__class__.__name__

    # DISABLED AS WE NEED TO UPDATE IT TO COPY toAppend().
    def _c_code_(self, node, name, inp, out, sub):
        x_name, index, toInsert = inp[0], inp[1], inp[2]
        output_name = out[0]
        fail = sub['fail']
        if not self.inplace:
            init = """
            %(output_name)s = (PyListObject*) PyList_GetSlice((PyObject*) %(x_name)s, 0, PyList_GET_SIZE((PyObject*) %(x_name)s)) ;
            """ % locals()
        else:
            init = """
            %(output_name)s =  %(x_name)s;
            """ % locals()
        return init + """
        if(%(output_name)s==NULL){
                %(fail)s
        };
        if(PyList_Insert((PyObject*) %(output_name)s, *((npy_int64 *) PyArray_DATA(%(index)s)), (PyObject*) %(toInsert)s)==-1){
            %(fail)s
        };
        Py_INCREF(%(output_name)s);
        """ % locals()

    def c_code_cache_version(self):
        return (1,)

insert = Insert()
"""
Insert an element at an index in a typed list.

:param x: the typed list to modify.
:param index: the index where to put the new element in `x`.
:param toInsert: The new element to insert.
"""


class Remove(Op):
    # See doc in instance of this Op after the class definition.
    def __init__(self, inplace=False):
        self.inplace = inplace
        if self.inplace:
            self.destroy_map = {0: [0]}
        else:
            self.view_map = {0: [0]}

    def __eq__(self, other):
        return type(self) == type(other) and self.inplace == other.inplace

    def __hash__(self):
        return hash(type(self)) ^ hash(self.inplace)

    def make_node(self, x, toRemove):
        assert isinstance(x.type, TypedListType)
        assert x.ttype == toRemove.type
        return Apply(self, [x, toRemove], [x.type()])

    def perform(self, node, (x, toRemove), (out, )):

        if not self.inplace:
            out[0] = list(x)
        else:
            out[0] = x

        """
        inelegant workaround for ValueError: The truth value of an
        array with more than one element is ambiguous. Use a.any() or a.all()
        being thrown when trying to remove a matrix from a matrices list
        """
        for y in range(out[0].__len__()):
                if node.inputs[0].ttype.values_eq(out[0][y], toRemove):
                    del out[0][y]
                    break

    def __str__(self):
        return self.__class__.__name__

remove = Remove()
"""Remove an element from a typed list.

:param x: the typed list to be changed.
:param toRemove: an element to be removed from the typed list.
    We only remove the first instance.

:note: Python implementation of remove doesn't work when we want to
    remove an ndarray from a list. This implementation works in that
    case.

"""


class Reverse(Op):
    # See doc in instance of this Op after the class definition.
    def __init__(self, inplace=False):
        self.inplace = inplace
        if self.inplace:
            self.destroy_map = {0: [0]}
        else:
            self.view_map = {0: [0]}

    def __eq__(self, other):
        return type(self) == type(other) and self.inplace == other.inplace

    def __hash__(self):
        return hash(type(self)) ^ hash(self.inplace)

    def make_node(self, x):
        assert isinstance(x.type, TypedListType)
        return Apply(self, [x], [x.type()])

    def perform(self, node, inp, (out, )):

        if not self.inplace:
            out[0] = list(inp[0])
        else:
            out[0] = inp[0]
        out[0].reverse()

    def __str__(self):
        return self.__class__.__name__

    def c_code(self, node, name, inp, out, sub):
        x_name = inp[0]
        output_name = out[0]
        fail = sub['fail']
        if not self.inplace:
            init = """
            %(output_name)s = (PyListObject*) PyList_GetSlice((PyObject*) %(x_name)s, 0, PyList_GET_SIZE((PyObject*) %(x_name)s)) ;
            """ % locals()
        else:
            init = """
            %(output_name)s =  %(x_name)s;
            """ % locals()
        return init + """
        if(%(output_name)s==NULL){
                %(fail)s
        };
        if(PyList_Reverse((PyObject*) %(output_name)s)==-1){
            %(fail)s
        };
        Py_INCREF(%(output_name)s);
        """ % locals()

    def c_code_cache_version(self):
        return (1,)

reverse = Reverse()
"""
Reverse the order of a typed list.

:param x: the typed list to be reversed.
"""


class Index(Op):
    # See doc in instance of this Op after the class definition.
    def __eq__(self, other):
        return type(self) == type(other)

    def __hash__(self):
        return hash(type(self))

    def make_node(self, x, elem):
        assert isinstance(x.type, TypedListType)
        assert x.ttype == elem.type
        return Apply(self, [x, elem], [T.scalar()])

    def perform(self, node, (x, elem), (out, )):
        """
        inelegant workaround for ValueError: The truth value of an
        array with more than one element is ambiguous. Use a.any() or a.all()
        being thrown when trying to remove a matrix from a matrices list
        """
        for y in range(len(x)):
            if node.inputs[0].ttype.values_eq(x[y], elem):
                out[0] = numpy.asarray(y, dtype=theano.config.floatX)
                break

    def __str__(self):
        return self.__class__.__name__

index_ = Index()


class Count(Op):
    # See doc in instance of this Op after the class definition.
    def __eq__(self, other):
        return type(self) == type(other)

    def __hash__(self):
        return hash(type(self))

    def make_node(self, x, elem):
        assert isinstance(x.type, TypedListType)
        assert x.ttype == elem.type
        return Apply(self, [x, elem], [T.scalar()])

    def perform(self, node, (x, elem), (out, )):
        """
        inelegant workaround for ValueError: The truth value of an
        array with more than one element is ambiguous. Use a.any() or a.all()
        being thrown when trying to remove a matrix from a matrices list
        """
        out[0] = 0
        for y in range(len(x)):
            if node.inputs[0].ttype.values_eq(x[y], elem):
                out[0] += 1
        out[0] = numpy.asarray(out[0], dtype=theano.config.floatX)

    def __str__(self):
        return self.__class__.__name__

count = Count()
"""
Count the number of times an element is in the typed list.

:param x: The typed list to look into.
:param elem: The element we want to count in list.
    The elements are compared with equals.

:note: Python implementation of count doesn't work when we want to
    count an ndarray from a list. This implementation works in that
    case.

"""


class Length(Op):
    # See doc in instance of this Op after the class definition.

    def __eq__(self, other):
        return type(self) == type(other)

    def __hash__(self):
        return hash(type(self))

    def make_node(self, x):
        assert isinstance(x.type, TypedListType)
        return Apply(self, [x], [T.scalar(dtype='int64')])

    def perform(self, node, x, (out, )):
        out[0] = numpy.asarray(len(x[0]), 'int64')

    def __str__(self):
        return self.__class__.__name__

    def c_code(self, node, name, inp, out, sub):
        x_name = inp[0]
        output_name = out[0]
        fail = sub['fail']
        return """
        if(!%(output_name)s)
            %(output_name)s=(PyArrayObject*)PyArray_EMPTY(0, NULL, NPY_INT64, 0);
        ((npy_int64*)PyArray_DATA(%(output_name)s))[0]=PyList_Size((PyObject*)%(x_name)s);
        Py_INCREF(%(output_name)s);
        """ % locals()

    def c_code_cache_version(self):
        return (1,)

length = Length()
"""
Returns the size of a list.

:param x: typed list.
"""
