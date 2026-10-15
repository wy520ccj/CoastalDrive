// 轴对称胎冠与真实有限凸面的有符号距离；双精度查询，不创建或推进物理世界。
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <cmath>
#include <cstdio>
#include <vector>
#include "BulletCollision/CollisionShapes/btConvexInternalShape.h"
#include "BulletCollision/NarrowPhaseCollision/btGjkEpa2.h"

class WheelProfile : public btConvexInternalShape {
    btVector3 axis;
    double radius, half, shoulder, crown;
public:
    WheelProfile(const btVector3& a,double r,double w,double s,double c)
        : axis(a.normalized()),radius(r),half(w/2-s),shoulder(s),crown(c) {
        m_shapeType=CUSTOM_CONVEX_SHAPE_TYPE; setMargin(0.);
    }
    btVector3 localGetSupportingVertexWithoutMargin(const btVector3& d) const override {
        const double axial=d.dot(axis);
        const btVector3 radial=d-axis*axial;
        const double rho=radial.length(), length=d.length();
        double x;
        if(crown && rho) x=btClamped(axial*half*half/(2*crown*rho),-half,half);
        else x=axial>0.?half:axial<0.?-half:0.;
        const double tread=radius-shoulder-crown*x*x/(half*half);
        return axis*x+(rho?radial*(tread/rho):btVector3(0,0,0))
            +(length?d*(shoulder/length):btVector3(0,0,0));
    }
    void batchedUnitVectorGetSupportingVertexWithoutMargin(const btVector3* d,btVector3* p,int n) const override {
        for(int i=0;i<n;++i)p[i]=localGetSupportingVertexWithoutMargin(d[i]);
    }
    void calculateLocalInertia(btScalar,btVector3& result) const override { result.setValue(0,0,0); }
    const char* getName() const override { return "AxisymmetricWheelProfile"; }
};

class SurfaceHull : public btConvexInternalShape {
    std::vector<btVector3> vertices;
    double rounding;
public:
    SurfaceHull(std::vector<btVector3> p,double margin):vertices(std::move(p)),rounding(margin) {
        m_shapeType=CUSTOM_CONVEX_SHAPE_TYPE; setMargin(0.);
    }
    btVector3 localGetSupportingVertexWithoutMargin(const btVector3& d) const override {
        btScalar value;
        const long i=d.maxDot(vertices.data(),(long)vertices.size(),value);
        const double length=d.length();
        return vertices[i]+(length?d*(rounding/length):btVector3(0,0,0));
    }
    void batchedUnitVectorGetSupportingVertexWithoutMargin(const btVector3* d,btVector3* p,int n) const override {
        for(int i=0;i<n;++i)p[i]=localGetSupportingVertexWithoutMargin(d[i]);
    }
    void calculateLocalInertia(btScalar,btVector3& result) const override { result.setValue(0,0,0); }
    const char* getName() const override { return "ActualSurfaceVertices"; }
};

static bool vector(PyObject* obj,btVector3& out) {
    PyObject* seq=PySequence_Fast(obj,"接触向量须为序列"); if(!seq)return false;
    if(PySequence_Fast_GET_SIZE(seq)!=3){Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"接触向量须有三个分量");return false;}
    double v[3];
    for(int i=0;i<3;++i){v[i]=PyFloat_AsDouble(PySequence_Fast_GET_ITEM(seq,i));if(PyErr_Occurred()){Py_DECREF(seq);return false;}}
    Py_DECREF(seq);
    if(!std::isfinite(v[0])||!std::isfinite(v[1])||!std::isfinite(v[2])){PyErr_SetString(PyExc_ValueError,"接触向量须为有限值");return false;}
    out.setValue(v[0],v[1],v[2]);return true;
}

static PyObject* signed_distance(PyObject*,PyObject* args) {
    PyObject *center_obj,*axis_obj,*vertices_obj;
    double radius,width,shoulder,crown,margin;
    if(!PyArg_ParseTuple(args,"OOOddddd",&center_obj,&axis_obj,&vertices_obj,&radius,&width,&shoulder,&crown,&margin))return nullptr;
    btVector3 center,axis;
    if(!vector(center_obj,center)||!vector(axis_obj,axis))return nullptr;
    if(axis.length2()==0. || !(radius>shoulder && width/2>shoulder && shoulder>=0. && crown>=0. && margin>=0.)
        ||!std::isfinite(radius+width+shoulder+crown+margin)){
        PyErr_SetString(PyExc_ValueError,"轮胎包络/有限面参数无效");return nullptr;
    }
    PyObject* seq=PySequence_Fast(vertices_obj,"有限凸面须为顶点序列"); if(!seq)return nullptr;
    const Py_ssize_t n=PySequence_Fast_GET_SIZE(seq);
    if(n<3){Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"有限凸面至少须有三个顶点");return nullptr;}
    std::vector<btVector3> vertices;vertices.reserve(n);
    for(Py_ssize_t i=0;i<n;++i){btVector3 point;if(!vector(PySequence_Fast_GET_ITEM(seq,i),point)){Py_DECREF(seq);return nullptr;}vertices.push_back(point);}
    Py_DECREF(seq);
    WheelProfile wheel(axis,radius,width,shoulder,crown);
    SurfaceHull surface(std::move(vertices),margin);
    btTransform a,b;a.setIdentity();b.setIdentity();a.setOrigin(center);
    btGjkEpaSolver2::sResults result;
    bool success;
    Py_BEGIN_ALLOW_THREADS
    success=btGjkEpaSolver2::SignedDistance(&wheel,a,&surface,b,btVector3(0,0,1),result);
    Py_END_ALLOW_THREADS
    if(!success){char error[160];std::snprintf(error,sizeof(error),"实际轮胎/凸面GJK-EPA有符号距离失败：状态%d",(int)result.status);PyErr_SetString(PyExc_ArithmeticError,error);return nullptr;}
    // EPA旧实现也会返回未收敛面；独立核对支持间隙，不把近似成功当已达精度。
    const btVector3 outward=-result.normal;
    const double gap=outward.dot(center+wheel.localGetSupportingVertexWithoutMargin(outward)
        -surface.localGetSupportingVertexWithoutMargin(-outward))+result.distance;
    if(result.distance<0. && gap>1e-11){char error[160];std::snprintf(error,sizeof(error),"径向EPA支持间隙未闭合：%.17g m",gap);PyErr_SetString(PyExc_ArithmeticError,error);return nullptr;}
    return Py_BuildValue("(d(ddd)(ddd)(ddd))",result.distance,
        result.normal.x(),result.normal.y(),result.normal.z(),
        result.witnesses[0].x(),result.witnesses[0].y(),result.witnesses[0].z(),
        result.witnesses[1].x(),result.witnesses[1].y(),result.witnesses[1].z());
}

static PyMethodDef methods[]={{"signed_distance",signed_distance,METH_VARARGS,"同一轴对称包络/有限凸面的深度、法线和见证点"},{nullptr}};
static PyModuleDef module={PyModuleDef_HEAD_INIT,"radial_contact_kernels",nullptr,-1,methods};
PyMODINIT_FUNC PyInit_radial_contact_kernels(void){return PyModule_Create(&module);}
