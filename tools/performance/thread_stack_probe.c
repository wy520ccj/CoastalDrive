#define WIN32_LEAN_AND_MEAN
#include <windows.h>

/* 只供本进程诊断；短暂停住指定线程，读取x64展开地址后必定恢复。 */
__declspec(dllexport) DWORD WINAPI capture_thread_stack(DWORD id, DWORD64 *frames, DWORD limit) {
    if (id == GetCurrentThreadId()) {
        SetLastError(ERROR_INVALID_PARAMETER);
        return 0;
    }
    HANDLE thread = OpenThread(THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME, FALSE, id);
    if (!thread) return 0;
    if (SuspendThread(thread) == (DWORD)-1) {
        DWORD error = GetLastError();
        CloseHandle(thread);
        SetLastError(error);
        return 0;
    }
    CONTEXT context = {0};
    context.ContextFlags = CONTEXT_FULL;
    DWORD count = 0, error = 0;
    __try {
        if (!GetThreadContext(thread, &context)) {
            error = GetLastError();
        } else {
            __try {
                while (context.Rip && count < limit) {
                    frames[count++] = context.Rip;
                    DWORD64 image = 0, old_sp = context.Rsp, establisher = 0;
                    PVOID handler = NULL;
                    PRUNTIME_FUNCTION entry = RtlLookupFunctionEntry(context.Rip, &image, NULL);
                    if (entry) {
                        RtlVirtualUnwind(UNW_FLAG_NHANDLER, image, context.Rip, entry,
                                         &context, &handler, &establisher, NULL);
                    } else {
                        SIZE_T read = 0;
                        if (!ReadProcessMemory(GetCurrentProcess(), (PVOID)context.Rsp,
                                               &context.Rip, sizeof(DWORD64), &read)) break;
                        context.Rsp += sizeof(DWORD64);
                    }
                    if (context.Rsp <= old_sp) break;
                }
            } __except(EXCEPTION_EXECUTE_HANDLER) {
                error = ERROR_INVALID_DATA;
            }
        }
    } __finally {
        ResumeThread(thread);
        CloseHandle(thread);
    }
    SetLastError(error);
    return count;
}
