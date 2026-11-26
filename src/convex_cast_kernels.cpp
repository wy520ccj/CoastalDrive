
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <vector>
#include <cmath>
#include "BulletCollision/CollisionShapes/btConvexInternalShape.h"
#include "BulletCollision/NarrowPhaseCollision/btContinuousConvexCollision.h"
#include "BulletCollision/NarrowPhaseCollision/btVoronoiSimplexSolver.h"
#include "BulletCollision/NarrowPhaseCollision/btGjkEpaPenetrationDepthSolver.h"

// 只查询原顶点凸体，不创建世界、不施力或积分。
class Points : public btConvexInternalShape {
public:
    std::vector<btVector3> points;
    bool wheel;
    Points(bool fast) : wheel(fast) { m_shapeType=CUSTOM_CONVEX_SHAPE_TYPE; }
    btVector3 localGetSupportingVertexWithoutMargin(const btVector3& d) const override {
        if (!wheel || std::hypot((double)d.y(),(double)d.z())*0.3 < std::abs((double)d.x())*0.1*1e-4) {
            btScalar value;
            long i=d.maxDot(points.data(),(long)points.size(),value);
            return points[i];
        }
        // 保留1088个单精度顶点；角度只定位相邻候选，最终仍逐顶点原浮点内积。
        const double pi=3.14159265358979323846;
        int angle=(int)std::floor(std::atan2((double)d.z(),(double)d.y())*32/pi);
        int selected=0;
        btScalar best=-BT_LARGE_FLOAT;
        for (int ring=0;ring<17;++ring) {
            for (int delta=-1;delta<=2;++delta) {
                int segment=(angle+delta+128)%64;
                int index=ring*64+segment;
                btScalar value=d.dot(points[index]);
                if (value>best || (value==best && index<selected)) { best=value;selected=index; }
            }
        }
        return points[selected];
    }
    void batchedUnitVectorGetSupportingVertexWithoutMargin(const btVector3* dirs,btVector3* out,int count) const override {
        for(int i=0;i<count;++i) out[i]=localGetSupportingVertexWithoutMargin(dirs[i]);
    }
    void calculateLocalInertia(btScalar mass,btVector3& inertia) const override { inertia.setValue(0,0,0); }
    const char* getName() const override { return "OriginalHullPoints"; }
};
static const char* capname="coastal.hull-cast";
static const char* api_capname="CoastalDrive.convex_cast_api.v1";
static void destroy(PyObject* obj) { delete (Points*)PyCapsule_GetPointer(obj,capname); }

typedef struct {
    int (*cast_points)(const void* wheel_ptr, const void* target_ptr,
                       const double from_pose[7], const double to_pose[7],
                       const double body_pose[7], const double shape_pose[7],
                       float ceiling, float* fraction_out, float normal_out[3], float point_out[3]);
    void (*hull_bounds)(const void* target_ptr, const double body_pose[7],
                        const double shape_pose[7], double low_out[3], double high_out[3]);
    const char* capsule_name;
} ConvexCastApi;

static void hull_bounds_native(const void* target_ptr, const double body_pose[7],
                               const double shape_pose[7], double low_out[3], double high_out[3]) {
    const Points* B = (const Points*)target_ptr;
    btTransform bp(btQuaternion((btScalar)body_pose[4], (btScalar)body_pose[5], (btScalar)body_pose[6], (btScalar)body_pose[3]),
                   btVector3((btScalar)body_pose[0], (btScalar)body_pose[1], (btScalar)body_pose[2]));
    btTransform cp(btQuaternion((btScalar)shape_pose[4], (btScalar)shape_pose[5], (btScalar)shape_pose[6], (btScalar)shape_pose[3]),
                   btVector3((btScalar)shape_pose[0], (btScalar)shape_pose[1], (btScalar)shape_pose[2]));
    btTransform other = bp * cp;
    double margin = (double)B->getMargin() + 1e-4;
    for (int a = 0; a < 3; ++a) { low_out[a] = 1e30; high_out[a] = -1e30; }
    for (const btVector3& pt : B->points) {
        btVector3 w = other * pt;
        double coords[3] = { (double)w.x(), (double)w.y(), (double)w.z() };
        for (int a = 0; a < 3; ++a) {
            if (coords[a] - margin < low_out[a]) low_out[a] = coords[a] - margin;
            if (coords[a] + margin > high_out[a]) high_out[a] = coords[a] + margin;
        }
    }
}

static int cast_points_native(const void* wheel_ptr, const void* target_ptr,
                              const double from_pose[7], const double to_pose[7],
                              const double body_pose[7], const double shape_pose[7],
                              float ceiling, float* fraction_out, float normal_out[3], float point_out[3]) {
    const Points* A = (const Points*)wheel_ptr;
    const Points* B = (const Points*)target_ptr;
    btTransform from(btQuaternion((btScalar)from_pose[4], (btScalar)from_pose[5], (btScalar)from_pose[6], (btScalar)from_pose[3]),
                     btVector3((btScalar)from_pose[0], (btScalar)from_pose[1], (btScalar)from_pose[2]));
    btTransform to(btQuaternion((btScalar)to_pose[4], (btScalar)to_pose[5], (btScalar)to_pose[6], (btScalar)to_pose[3]),
                   btVector3((btScalar)to_pose[0], (btScalar)to_pose[1], (btScalar)to_pose[2]));
    btTransform bp(btQuaternion((btScalar)body_pose[4], (btScalar)body_pose[5], (btScalar)body_pose[6], (btScalar)body_pose[3]),
                   btVector3((btScalar)body_pose[0], (btScalar)body_pose[1], (btScalar)body_pose[2]));
    btTransform cp(btQuaternion((btScalar)shape_pose[4], (btScalar)shape_pose[5], (btScalar)shape_pose[6], (btScalar)shape_pose[3]),
                   btVector3((btScalar)shape_pose[0], (btScalar)shape_pose[1], (btScalar)shape_pose[2]));
    btTransform other = bp * cp;
    btVoronoiSimplexSolver simplex;
    btGjkEpaPenetrationDepthSolver penetration;
    btContinuousConvexCollision caster(A, B, &simplex, &penetration);
    btConvexCast::CastResult result;
    result.m_fraction = ceiling;
    result.m_allowedPenetration = 0.f;
    bool hit = caster.calcTimeOfImpact(from, to, other, other, result);
    if (!hit || result.m_normal.length2() <= .0001f || result.m_fraction >= ceiling)
        return 0;
    result.m_normal.normalize();
    *fraction_out = result.m_fraction;
    normal_out[0] = result.m_normal.x();
    normal_out[1] = result.m_normal.y();
    normal_out[2] = result.m_normal.z();
    point_out[0] = result.m_hitPoint.x();
    point_out[1] = result.m_hitPoint.y();
    point_out[2] = result.m_hitPoint.z();
    return 1;
}
static ConvexCastApi convex_cast_api = { cast_points_native, hull_bounds_native, "coastal.hull-cast" };
static bool values(PyObject* obj,double* out,int count) {
    PyObject* seq=PySequence_Fast(obj,"向量须为序列"); if(!seq)return false;
    if(PySequence_Fast_GET_SIZE(seq)!=count) { Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"向量维数不一致");return false; }
    for(int i=0;i<count;++i) { out[i]=PyFloat_AsDouble(PySequence_Fast_GET_ITEM(seq,i));if(PyErr_Occurred()){Py_DECREF(seq);return false;} }
    Py_DECREF(seq);return true;
}
static PyObject* hull(PyObject*,PyObject* args) {
    PyObject* src;double margin;int fast=0;
    if(!PyArg_ParseTuple(args,"Od|p",&src,&margin,&fast))return nullptr;
    PyObject* seq=PySequence_Fast(src,"凸体顶点须为序列");if(!seq)return nullptr;
    Py_ssize_t n=PySequence_Fast_GET_SIZE(seq);
    if(!n || (fast && n!=1088)) {Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"原胎冠顶点数不一致");return nullptr;}
    Points* shape=new Points(fast); shape->setMargin((btScalar)margin);
    shape->points.reserve(n);
    for(Py_ssize_t i=0;i<n;++i){double v[3];if(!values(PySequence_Fast_GET_ITEM(seq,i),v,3)){delete shape;Py_DECREF(seq);return nullptr;}shape->points.emplace_back((btScalar)v[0],(btScalar)v[1],(btScalar)v[2]);}
    Py_DECREF(seq);return PyCapsule_New(shape,capname,destroy);
}
static bool transform(PyObject* obj,btTransform& out) {
    double v[7];if(!values(obj,v,7))return false;
    out=btTransform(btQuaternion((btScalar)v[4],(btScalar)v[5],(btScalar)v[6],(btScalar)v[3]),btVector3((btScalar)v[0],(btScalar)v[1],(btScalar)v[2]));return true;
}
static PyObject* cast(PyObject*,PyObject* args) {
    PyObject *a,*b,*f,*t,*target;float ceiling=1.;
    if(!PyArg_ParseTuple(args,"OOOOO|f",&a,&b,&f,&t,&target,&ceiling))return nullptr;
    Points* A=(Points*)PyCapsule_GetPointer(a,capname);if(!A)return nullptr;
    Points* B=(Points*)PyCapsule_GetPointer(b,capname);if(!B)return nullptr;
    btTransform from,to,other;
    if(!transform(f,from)||!transform(t,to))return nullptr;
    PyObject* target_seq=PySequence_Fast(target,"凸体变换须为序列");if(!target_seq)return nullptr;
    if(PySequence_Fast_GET_SIZE(target_seq)!=14) {Py_DECREF(target_seq);PyErr_SetString(PyExc_ValueError,"凸体变换维数不一致");return nullptr;}
    PyObject* body=PySequence_GetSlice(target_seq,0,7);
    PyObject* child=PySequence_GetSlice(target_seq,7,14);
    Py_DECREF(target_seq);
    btTransform body_pose,child_pose;
    bool ok=body && child && transform(body,body_pose) && transform(child,child_pose);
    Py_XDECREF(body);Py_XDECREF(child);if(!ok)return nullptr;
    other=body_pose*child_pose;
    btVoronoiSimplexSolver simplex;
    btGjkEpaPenetrationDepthSolver penetration;
    btContinuousConvexCollision caster(A,B,&simplex,&penetration);
    btConvexCast::CastResult result;result.m_fraction=ceiling;result.m_allowedPenetration=0.;
    bool hit;
    Py_BEGIN_ALLOW_THREADS
    hit=caster.calcTimeOfImpact(from,to,other,other,result);
    Py_END_ALLOW_THREADS
    if(!hit || result.m_normal.length2()<=.0001f || result.m_fraction>=ceiling)Py_RETURN_NONE;
    result.m_normal.normalize();
    return Py_BuildValue("(f(fff)(fff))",result.m_fraction,result.m_normal.x(),result.m_normal.y(),result.m_normal.z(),result.m_hitPoint.x(),result.m_hitPoint.y(),result.m_hitPoint.z());
}
static PyObject* support(PyObject*,PyObject* args){PyObject* cap,*direction;if(!PyArg_ParseTuple(args,"OO",&cap,&direction))return nullptr;Points*shape=(Points*)PyCapsule_GetPointer(cap,capname);if(!shape)return nullptr;double v[3];if(!values(direction,v,3))return nullptr;auto p=shape->localGetSupportingVertexWithoutMargin(btVector3(v[0],v[1],v[2]));return Py_BuildValue("(fff)",p.x(),p.y(),p.z());}
static PyMethodDef methods[]={{"hull",hull,METH_VARARGS,nullptr},{"cast",cast,METH_VARARGS,nullptr},{"support",support,METH_VARARGS,nullptr},{nullptr}};
static PyModuleDef module={PyModuleDef_HEAD_INIT,"convex_cast_kernels",nullptr,-1,methods};
PyMODINIT_FUNC PyInit_convex_cast_kernels(void){
    PyObject* mod=PyModule_Create(&module);
    if(!mod)return nullptr;
    PyObject* api=PyCapsule_New(&convex_cast_api,api_capname,nullptr);
    if(!api || PyModule_AddObject(mod,"_convex_cast_api",api)<0){Py_XDECREF(api);Py_DECREF(mod);return nullptr;}
    return mod;
}
