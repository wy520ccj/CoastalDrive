#ifndef COASTAL_JOINT_CONTACT_API_H
#define COASTAL_JOINT_CONTACT_API_H
/* 准备阶段读取Python对象；迭代只传数值，当前仍持GIL以报告原异常。 */
typedef struct {
    int (*evaluate)(void *,const double *,const double *,double,double *,double *,double *);
} JointContactApi;
#define JOINT_CONTACT_API_NAME "CoastalDrive.joint_contact_api.v1"
#define JOINT_CONTACT_PACKET_NAME "CoastalDrive.joint_contact_packet.v1"
#endif
