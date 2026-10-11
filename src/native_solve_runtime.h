#ifndef COASTAL_NATIVE_SOLVE_RUNTIME_H
#define COASTAL_NATIVE_SOLVE_RUNTIME_H
#include <string.h>
/* 纯数值区只记录原异常；恢复线程状态之后再创建Python异常。 */
typedef struct { PyObject *type; char message[512]; } NativeSolveError;
#ifdef _MSC_VER
static __declspec(thread) NativeSolveError *native_solve_error;
#else
static _Thread_local NativeSolveError *native_solve_error;
#endif
static void native_error_set(PyObject *type,const char *message) {
    if(!native_solve_error){PyErr_SetString(type,message);return;}
    if(native_solve_error->type)return;
    native_solve_error->type=type;
    size_t length=strlen(message);if(length>=sizeof(native_solve_error->message))length=sizeof(native_solve_error->message)-1;
    memcpy(native_solve_error->message,message,length);native_solve_error->message[length]=0;
}
static PyObject *native_error_occurred(void) {
    return native_solve_error ? native_solve_error->type : PyErr_Occurred();
}
static PyObject *native_no_memory(void) {
    if(!native_solve_error)return PyErr_NoMemory();
    native_error_set(PyExc_MemoryError,"");return NULL;
}
#define PyErr_SetString native_error_set
#define PyErr_Occurred native_error_occurred
#define PyErr_NoMemory native_no_memory
#endif
