#ifndef COASTAL_JOINT_CONTACT_API_H
#define COASTAL_JOINT_CONTACT_API_H
/* 准备持GIL，连续数值区用线程局部错误记录，完成后恢复原异常。 */
#include "native_solve_runtime.h"
typedef struct {
    int (*evaluate)(void *,const double *,const double *,double,double *,double *,double *);
    void (*begin)(NativeSolveError *);
    void (*end)(void);
    int (*queries_world)(void *);
} JointContactApi;
#define JOINT_CONTACT_API_NAME "CoastalDrive.joint_contact_api.v4"
#define JOINT_CONTACT_PACKET_NAME "CoastalDrive.joint_contact_packet.v1"
#endif
