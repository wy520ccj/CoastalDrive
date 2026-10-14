// 双精度接触查询独占编译单元，避免与既有单精度模块复用同名目标文件。
#include "../vendor/bullet-2.84/BulletCollision/CollisionShapes/btSphereShape.cpp"
#include "../vendor/bullet-2.84/BulletCollision/CollisionShapes/btCollisionShape.cpp"
#include "../vendor/bullet-2.84/BulletCollision/CollisionShapes/btConvexShape.cpp"
#include "../vendor/bullet-2.84/BulletCollision/CollisionShapes/btConvexInternalShape.cpp"
#include "radial_gjk_epa.cpp"
#include "../vendor/bullet-2.84/LinearMath/btAlignedAllocator.cpp"
#include "../vendor/bullet-2.84/LinearMath/btVector3.cpp"
