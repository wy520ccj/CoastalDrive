/* 固定车辆数值包：保留double位型和记录字段次序，不执行物理运算。 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

typedef struct { PyObject *types, *names; uint64_t signature; } Layout;
typedef struct { char *data; size_t length, capacity; } Writer;
typedef struct { const unsigned char *data; size_t offset, length; } Reader;

static int append(Writer *w, const void *data, size_t size) {
    if (size > (size_t)PY_SSIZE_T_MAX - w->length) { PyErr_NoMemory(); return -1; }
    size_t needed = w->length + size;
    if (needed > w->capacity) {
        size_t capacity = needed > w->capacity * 2 ? needed : w->capacity * 2;
        char *grown = PyMem_Realloc(w->data, capacity);
        if (!grown) { PyErr_NoMemory(); return -1; }
        w->data = grown; w->capacity = capacity;
    }
    memcpy(w->data + w->length, data, size); w->length = needed;
    return 0;
}
static int put_integer(Writer *w, uint64_t value, int bytes) {
    unsigned char data[8];
    for (int i=0; i<bytes; ++i) data[i] = (unsigned char)(value >> (8*i));
    return append(w,data,(size_t)bytes);
}
static int read_integer(Reader *r, uint64_t *value, int bytes) {
    if ((size_t)bytes > r->length-r->offset) {
        PyErr_SetString(PyExc_ValueError,"车辆数值包被截断"); return -1;
    }
    *value=0;
    for (int i=0; i<bytes; ++i) *value |= ((uint64_t)r->data[r->offset++]) << (8*i);
    return 0;
}
static int count(Writer *w, Py_ssize_t length) {
    if (length > UINT32_MAX) { PyErr_SetString(PyExc_OverflowError,"车辆数值包字段过大"); return -1; }
    return put_integer(w,(uint64_t)length,4);
}
static int pack(Layout *layout, Writer *w, PyObject *value);
static int pack_impl(Layout *layout, Writer *w, PyObject *value) {
    if (value==Py_None) return put_integer(w,0,1);
    if (value==Py_False) return put_integer(w,1,1);
    if (value==Py_True) return put_integer(w,2,1);
    if (PyFloat_Check(value)) {
        double number=PyFloat_AS_DOUBLE(value); uint64_t bits;
        memcpy(&bits,&number,8);
        return put_integer(w,3,1) || put_integer(w,bits,8) ? -1 : 0;
    }
    if (PyLong_Check(value)) {
        long long number=PyLong_AsLongLong(value);
        if (number==-1 && PyErr_Occurred()) return -1;
        return put_integer(w,4,1) || put_integer(w,(uint64_t)number,8) ? -1 : 0;
    }
    if (PyUnicode_Check(value)) {
        Py_ssize_t size; const char *data=PyUnicode_AsUTF8AndSize(value,&size);
        if (!data) return -1;
        return put_integer(w,5,1) || count(w,size) || append(w,data,(size_t)size) ? -1 : 0;
    }
    if (PyTuple_Check(value) || PyList_Check(value)) {
        int tuple=PyTuple_Check(value);
        Py_ssize_t size=tuple ? PyTuple_GET_SIZE(value) : PyList_GET_SIZE(value);
        if (put_integer(w,tuple?6:7,1) || count(w,size)) return -1;
        for (Py_ssize_t i=0; i<size; ++i)
            if (pack(layout,w,tuple?PyTuple_GET_ITEM(value,i):PyList_GET_ITEM(value,i))) return -1;
        return 0;
    }
    if (PyDict_Check(value)) {
        if (put_integer(w,8,1) || count(w,PyDict_Size(value))) return -1;
        Py_ssize_t position=0; PyObject *key,*item;
        while (PyDict_Next(value,&position,&key,&item))
            if (pack(layout,w,key) || pack(layout,w,item)) return -1;
        return 0;
    }
    for (Py_ssize_t i=0; i<PyTuple_GET_SIZE(layout->types); ++i) {
        if ((PyObject *)Py_TYPE(value) != PyTuple_GET_ITEM(layout->types,i)) continue;
        if (put_integer(w,32+(uint64_t)i,1)) return -1;
        PyObject *values=PyObject_GenericGetDict(value,NULL);
        if (!values) return -1;
        PyObject *names=PyTuple_GET_ITEM(layout->names,i);
        for (Py_ssize_t j=0; j<PyTuple_GET_SIZE(names); ++j) {
            PyObject *name=PyTuple_GET_ITEM(names,j);
            PyObject *item=PyDict_GetItemWithError(values,name);
            if (!item) {
                if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError,"车辆数值记录缺字段");
                Py_DECREF(values); return -1;
            }
            if (pack(layout,w,item)) { Py_DECREF(values); return -1; }
        }
        Py_DECREF(values); return 0;
    }
    PyErr_SetString(PyExc_TypeError,"车辆数值包不接受此类型");
    return -1;
}
static int pack(Layout *layout, Writer *w, PyObject *value) {
    if (Py_EnterRecursiveCall(" while packing vehicle input")) return -1;
    int result=pack_impl(layout,w,value);
    Py_LeaveRecursiveCall(); return result;
}
static PyObject *unpack(Layout *layout, Reader *r);
static PyObject *unpack_impl(Layout *layout, Reader *r) {
    uint64_t tag,size;
    if (read_integer(r,&tag,1)) return NULL;
    if (tag==0) Py_RETURN_NONE;
    if (tag==1) Py_RETURN_FALSE;
    if (tag==2) Py_RETURN_TRUE;
    if (tag==3 || tag==4) {
        if (read_integer(r,&size,8)) return NULL;
        if (tag==4) { int64_t number; memcpy(&number,&size,8); return PyLong_FromLongLong(number); }
        double number; memcpy(&number,&size,8); return PyFloat_FromDouble(number);
    }
    if (tag>=5 && tag<=8) {
        if (read_integer(r,&size,4)) return NULL;
        if (size > r->length-r->offset) { PyErr_SetString(PyExc_ValueError,"车辆数值包长度无效"); return NULL; }
        if (tag==5) {
            PyObject *text=PyUnicode_DecodeUTF8((const char *)r->data+r->offset,(Py_ssize_t)size,"strict");
            r->offset+=(size_t)size; return text;
        }
        PyObject *result=tag==6 ? PyTuple_New((Py_ssize_t)size) : tag==7 ? PyList_New((Py_ssize_t)size) : PyDict_New();
        if (!result) return NULL;
        for (uint64_t i=0; i<size; ++i) {
            PyObject *item=unpack(layout,r);
            if (!item) { Py_DECREF(result); return NULL; }
            if (tag==6) PyTuple_SET_ITEM(result,(Py_ssize_t)i,item);
            else if (tag==7) PyList_SET_ITEM(result,(Py_ssize_t)i,item);
            else {
                PyObject *value=unpack(layout,r);
                int failed=!value || PyDict_SetItem(result,item,value);
                Py_DECREF(item); Py_XDECREF(value);
                if (failed) { Py_DECREF(result); return NULL; }
            }
        }
        return result;
    }
    if (tag>=32 && tag-32 < (uint64_t)PyTuple_GET_SIZE(layout->types)) {
        PyTypeObject *type=(PyTypeObject *)PyTuple_GET_ITEM(layout->types,(Py_ssize_t)tag-32);
        PyObject *names=PyTuple_GET_ITEM(layout->names,(Py_ssize_t)tag-32), *values=PyDict_New();
        if (!values) return NULL;
        for (Py_ssize_t i=0; i<PyTuple_GET_SIZE(names); ++i) {
            PyObject *value=unpack(layout,r);
            int failed=!value || PyDict_SetItem(values,PyTuple_GET_ITEM(names,i),value);
            Py_XDECREF(value);
            if (failed) { Py_DECREF(values); return NULL; }
        }
        /* 与pickle一样恢复已确认字段，不重新执行frozen dataclass构造。 */
        PyObject *result=PyType_GenericAlloc(type,0);
        if (result && PyObject_GenericSetDict(result,values,NULL)) Py_CLEAR(result);
        Py_DECREF(values); return result;
    }
    PyErr_SetString(PyExc_ValueError,"未知车辆数值包字段类型"); return NULL;
}
static PyObject *unpack(Layout *layout, Reader *r) {
    if (Py_EnterRecursiveCall(" while unpacking vehicle input")) return NULL;
    PyObject *result=unpack_impl(layout,r);
    Py_LeaveRecursiveCall(); return result;
}
static void destroy_layout(PyObject *capsule) {
    Layout *layout=PyCapsule_GetPointer(capsule,"coastaldrive.physics_layout");
    if (layout) { Py_DECREF(layout->types); Py_DECREF(layout->names); PyMem_Free(layout); }
}
static PyObject *make_layout(PyObject *self, PyObject *args) {
    PyObject *types,*names; unsigned long long signature;
    if (!PyArg_ParseTuple(args,"O!O!K",&PyTuple_Type,&types,&PyTuple_Type,&names,&signature)) return NULL;
    Py_ssize_t size=PyTuple_GET_SIZE(types);
    if (size<1 || size>224 || size!=PyTuple_GET_SIZE(names)) {
        PyErr_SetString(PyExc_ValueError,"车辆数值包记录布局不一致"); return NULL;
    }
    for (Py_ssize_t i=0; i<size; ++i) {
        PyObject *type=PyTuple_GET_ITEM(types,i), *fields=PyTuple_GET_ITEM(names,i);
        if (!PyType_Check(type) || !(((PyTypeObject *)type)->tp_flags & Py_TPFLAGS_HEAPTYPE) || !PyTuple_Check(fields)) {
            PyErr_SetString(PyExc_TypeError,"车辆数值包需要Python记录类与字段元组"); return NULL;
        }
        for (Py_ssize_t j=0; j<PyTuple_GET_SIZE(fields); ++j)
            if (!PyUnicode_Check(PyTuple_GET_ITEM(fields,j))) {
                PyErr_SetString(PyExc_TypeError,"车辆数值包字段名必须是字符串"); return NULL;
            }
    }
    Layout *layout=PyMem_Malloc(sizeof(Layout));
    if (!layout) return PyErr_NoMemory();
    layout->types=Py_NewRef(types); layout->names=Py_NewRef(names); layout->signature=signature;
    PyObject *capsule=PyCapsule_New(layout,"coastaldrive.physics_layout",destroy_layout);
    if (!capsule) { Py_DECREF(types); Py_DECREF(names); PyMem_Free(layout); }
    return capsule;
}
static PyObject *encode(PyObject *self, PyObject *args) {
    PyObject *capsule,*value;
    if (!PyArg_ParseTuple(args,"OO",&capsule,&value)) return NULL;
    Layout *layout=PyCapsule_GetPointer(capsule,"coastaldrive.physics_layout");
    if (!layout) return NULL;
    Writer writer={NULL,0,0}; PyObject *result=NULL;
    if (!append(&writer,"CDP1",4) && !put_integer(&writer,layout->signature,8) && !pack(layout,&writer,value))
        result=PyBytes_FromStringAndSize(writer.data,(Py_ssize_t)writer.length);
    PyMem_Free(writer.data); return result;
}
static PyObject *decode(PyObject *self, PyObject *args) {
    PyObject *capsule; Py_buffer buffer;
    if (!PyArg_ParseTuple(args,"Oy*",&capsule,&buffer)) return NULL;
    Layout *layout=PyCapsule_GetPointer(capsule,"coastaldrive.physics_layout"); PyObject *result=NULL;
    if (!layout) goto done;
    Reader reader={(const unsigned char *)buffer.buf,0,(size_t)buffer.len}; uint64_t signature;
    if (reader.length<12 || memcmp(reader.data,"CDP1",4)) {
        PyErr_SetString(PyExc_ValueError,"车辆数值包版本无效"); goto done;
    }
    reader.offset=4;
    if (read_integer(&reader,&signature,8)) goto done;
    if (signature!=layout->signature) { PyErr_SetString(PyExc_ValueError,"车辆数值包布局不匹配"); goto done; }
    result=unpack(layout,&reader);
    if (result && reader.offset!=reader.length) {
        Py_CLEAR(result); PyErr_SetString(PyExc_ValueError,"车辆数值包末尾含多余数据");
    }
done:
    PyBuffer_Release(&buffer); return result;
}
static PyMethodDef methods[]={{"layout",make_layout,METH_VARARGS,NULL},{"encode",encode,METH_VARARGS,NULL},
    {"decode",decode,METH_VARARGS,NULL},{NULL,NULL,0,NULL}};
static struct PyModuleDef module={PyModuleDef_HEAD_INIT,"physics_packet_kernels",NULL,-1,methods};
PyMODINIT_FUNC PyInit_physics_packet_kernels(void) { return PyModule_Create(&module); }
