// 独立恒力世界的精度对照；不连接或修改生产物理世界。
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <initializer_list>
#include "btBulletDynamicsCommon.h"

static PyObject* check(PyObject*, PyObject*) {
    PyObject* rows = PyList_New(0);
    for (double force : {-0.02,-20.,-300.}) for (int substeps : {2,4,8}) for (int mode=0;mode<2;++mode) {
        btDefaultCollisionConfiguration configuration;
        btCollisionDispatcher dispatcher(&configuration);
        btDbvtBroadphase broadphase;
        btSequentialImpulseConstraintSolver solver;
        btDiscreteDynamicsWorld world(&dispatcher,&broadphase,&solver,&configuration);
        world.setGravity(btVector3(0,0,0));
        btSphereShape shape(0);
        shape.setMargin(0);
        btRigidBody::btRigidBodyConstructionInfo info(btScalar(1040),nullptr,&shape,btVector3(0,0,0));
        btRigidBody body(info);
        body.setLinearVelocity(btVector3(0,5,0));
        body.setActivationState(DISABLE_DEACTIVATION);
        world.addRigidBody(&body);
        const btScalar dt = btScalar(1./(120*substeps));
        for (int step=0;step<120*substeps;++step) {
            if(mode==0) {
                body.applyCentralImpulse(btVector3(0,btScalar(.625*force/(120*substeps)),0));
                body.applyCentralForce(btVector3(0,btScalar(.375*force),0));
            } else body.applyCentralForce(btVector3(0,btScalar(force),0));
            world.stepSimulation(dt,0,dt);
        }
        const double actual=body.getLinearVelocity().y(),expected=5.+force/1040.;
        PyObject* row=Py_BuildValue("{s:d,s:i,s:s,s:d,s:d,s:d,s:d,s:i}",
            "force_N",force,"substeps",substeps,"mode",mode==0?"impulse_then_force":"all_force",
            "velocity_mps",actual,"analytic_mps",expected,"velocity_error",actual-expected,
            "kinetic_defect_J",.5*1040*(actual-expected)*(actual+expected),"scalar_bytes",int(sizeof(btScalar)));
        if(!row || PyList_Append(rows,row)<0){Py_XDECREF(row);Py_DECREF(rows);return nullptr;}
        Py_DECREF(row);
        world.removeRigidBody(&body);
    }
    return rows;
}
static PyMethodDef methods[]={{"check",check,METH_NOARGS,nullptr},{nullptr,nullptr,0,nullptr}};
#ifdef BT_USE_DOUBLE_PRECISION
static PyModuleDef module={PyModuleDef_HEAD_INIT,"bullet_precision_double",nullptr,-1,methods};
PyMODINIT_FUNC PyInit_bullet_precision_double(){return PyModule_Create(&module);}
#else
static PyModuleDef module={PyModuleDef_HEAD_INIT,"bullet_precision_float",nullptr,-1,methods};
PyMODINIT_FUNC PyInit_bullet_precision_float(){return PyModule_Create(&module);}
#endif
