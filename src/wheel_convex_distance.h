/* 有限胎宽凸体距离：原支持判据、部分和、96轮上限与SVD投影保持。 */
typedef struct { double point[3], body[3]; } WheelVertex;
typedef struct {
    double center[3], axis[3], radius, half, crown;
    double (*polygon)[3], box[3];
    Py_ssize_t count;
    PyObject *support, *coordinates;
} WheelConvex;

static int wheel_same(double a[3], double b[3]) {
    return a[0]==b[0] && a[1]==b[1] && a[2]==b[2];
}

static int wheel_body(WheelConvex *shape, double direction[3], double result[3]) {
    if (shape->support) {
        PyObject *input=Py_BuildValue("(ddd)",direction[0],direction[1],direction[2]);
        if (!input) return 0;
        PyObject *value=PyObject_CallOneArg(shape->support,input); Py_DECREF(input);
        if (!value) return 0;
        int ok=vector(value,result); Py_DECREF(value); return ok;
    }
    if (!shape->polygon) {
        for (int i=0;i<3;++i) result[i]=direction[i]!=0. ? copysign(shape->box[i],direction[i]) : 0.;
    } else {
        Py_ssize_t selected=0;
        double best=dot(shape->polygon[0],direction);
        for (Py_ssize_t i=1;i<shape->count;++i) {
            double projection=dot(shape->polygon[i],direction);
            if (projection>best) { best=projection; selected=i; }
        }
        for (int i=0;i<3;++i) result[i]=shape->polygon[selected][i];
    }
    return 1;
}

static int wheel_support(WheelConvex *shape, double direction[3], WheelVertex *vertex) {
    double negative[3],offset[3];
    for (int i=0;i<3;++i) negative[i]=-direction[i];
    if (!support_values(negative,shape->axis,shape->radius,shape->half,0.,shape->crown,offset)
        || !wheel_body(shape,direction,vertex->body)) return 0;
    for (int i=0;i<3;++i) {
        double terms[4]={shape->center[i],-vertex->body[i],offset[i],0.};
        vertex->point[i]=sum_four(terms);
    }
    return !PyErr_Occurred();
}

/* 良态双列使用补偿叉积投影；近共线和三列单纯形沿用原SVD。 */
static int wheel_coordinates(WheelConvex *shape, double columns[3][3], int count,
                             double rhs[3], double values[3], int *rank) {
    if (count==2) {
        double normal[3],first[3],second[3];
        cross_precise(columns[0],columns[1],normal);
        double squared=exact_dot(normal,normal);
        double scale=exact_dot(columns[0],columns[0])*exact_dot(columns[1],columns[1]);
        if (squared>1e-6*scale) {
            cross_precise(rhs,columns[1],first);
            cross_precise(columns[0],rhs,second);
            values[0]=exact_dot(first,normal)/squared;
            values[1]=exact_dot(second,normal)/squared;
            *rank=2;
            return !PyErr_Occurred();
        }
    }
    /* 连续内核直接求小型SVD；原独立入口仍保留原NumPy边界。 */
    if(shape->coordinates==Py_None) {
        double matrix[3][3],rotation[3][3]={{0.}},squared[3];
        for(int i=0;i<count;++i){rotation[i][i]=1.;for(int a=0;a<3;++a)matrix[i][a]=columns[i][a];}
        for(int sweep=0;sweep<40;++sweep) {
            int changed=0;
            for(int i=0;i<count;++i)for(int j=i+1;j<count;++j) {
                double aa=exact_dot(matrix[i],matrix[i]),bb=exact_dot(matrix[j],matrix[j]),ab=exact_dot(matrix[i],matrix[j]);
                if(ab==0.||fabs(ab)<=2.220446049250313e-16*sqrt(aa)*sqrt(bb))continue;
                double tau=(bb-aa)/(2*ab),t=copysign(1.,tau)/(fabs(tau)+hypot(1.,tau)),c=1/sqrt(1+t*t),d=c*t;
                for(int a=0;a<3;++a){double x=matrix[i][a],y=matrix[j][a];matrix[i][a]=c*x-d*y;matrix[j][a]=d*x+c*y;}
                for(int a=0;a<count;++a){double x=rotation[i][a],y=rotation[j][a];rotation[i][a]=c*x-d*y;rotation[j][a]=d*x+c*y;}
                changed=1;
            }
            if(!changed)break;
        }
        double largest=0.;
        for(int i=0;i<count;++i){squared[i]=exact_dot(matrix[i],matrix[i]);if(squared[i]>largest)largest=squared[i];values[i]=0.;}
        double threshold=pow(3*2.220446049250313e-16,2.)*largest;*rank=0;
        for(int i=0;i<count;++i)if(squared[i]>threshold) {
            ++*rank;double projection=exact_dot(matrix[i],rhs)/squared[i];
            for(int a=0;a<count;++a)values[a]+=rotation[i][a]*projection;
        }
        return 1;
    }
    PyObject *matrix=PyTuple_New(count);
    if (!matrix) return 0;
    for (int i=0;i<count;++i) {
        PyObject *column=Py_BuildValue("(ddd)",columns[i][0],columns[i][1],columns[i][2]);
        if (!column) { Py_DECREF(matrix); return 0; }
        PyTuple_SET_ITEM(matrix,i,column);
    }
    PyObject *input=Py_BuildValue("(ddd)",rhs[0],rhs[1],rhs[2]);
    if (!input) { Py_DECREF(matrix); return 0; }
    PyObject *result=PyObject_CallFunctionObjArgs(shape->coordinates,matrix,input,NULL);
    Py_DECREF(matrix); Py_DECREF(input);
    if (!result) return 0;
    PyObject *coordinates=PyTuple_GET_ITEM(result,0);
    *rank=(int)PyLong_AsLong(PyTuple_GET_ITEM(result,1));
    for (int i=0;i<count;++i) values[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(coordinates,i));
    Py_DECREF(result); return !PyErr_Occurred();
}

static void wheel_segment(double a[3],double b[3],double point[3],double weights[2]) {
    double delta[3]; subtract(b,a,delta);
    double length=dot(delta,delta),t=length!=0. ? -dot(a,delta)/length : 0.;
    if (t>1.) t=1.; if (t<0.) t=0.;
    for (int i=0;i<3;++i) point[i]=a[i]+t*delta[i];
    weights[0]=1.-t; weights[1]=t;
}

static int wheel_triangle(WheelConvex *shape,double a[3],double b[3],double c[3],
                          double point[3],double weights[3]) {
    double columns[3][3],rhs[3],values[3]; int rank;
    subtract(b,a,columns[0]); subtract(c,a,columns[1]);
    for (int i=0;i<3;++i) rhs[i]=-a[i];
    if (!wheel_coordinates(shape,columns,2,rhs,values,&rank)) return 0;
    double v=values[0],w=values[1];
    if (rank==2 && v>=0. && w>=0. && v+w<=1.) {
        weights[0]=1.-v-w; weights[1]=v; weights[2]=w;
        double normal[3]; cross_precise(columns[0],columns[1],normal);
        double height=exact_dot(normal,a)/dot(normal,normal);
        for (int i=0;i<3;++i) point[i]=height*normal[i];
    } else {
        double *points[3]={a,b,c},best=INFINITY;
        const int pairs[3][2]={{0,1},{0,2},{1,2}};
        for (int k=0;k<3;++k) {
            double candidate[3],local[2];
            wheel_segment(points[pairs[k][0]],points[pairs[k][1]],candidate,local);
            double squared=dot(candidate,candidate);
            if (k==0 || squared<best) {
                best=squared;
                for (int i=0;i<3;++i) { point[i]=candidate[i]; weights[i]=0.; }
                weights[pairs[k][0]]=local[0]; weights[pairs[k][1]]=local[1];
            }
        }
    }
    return !PyErr_Occurred();
}

static int wheel_closest(WheelConvex *shape,WheelVertex vertices[4],int count,double point[3],double weights[4]) {
    if (count==1) {
        for (int i=0;i<3;++i) point[i]=vertices[0].point[i];
        weights[0]=1.; return 1;
    }
    if (count==2) { wheel_segment(vertices[0].point,vertices[1].point,point,weights); return 1; }
    if (count==3) return wheel_triangle(shape,vertices[0].point,vertices[1].point,vertices[2].point,point,weights);
    double columns[3][3],rhs[3],values[3]; int rank;
    for (int i=0;i<3;++i) { subtract(vertices[i+1].point,vertices[0].point,columns[i]); rhs[i]=-vertices[0].point[i]; }
    if (!wheel_coordinates(shape,columns,3,rhs,values,&rank)) return 0;
    double u=values[0],v=values[1],w=values[2];
    if (rank==3 && u>=0. && v>=0. && w>=0. && u+v+w<=1.) {
        for (int i=0;i<3;++i) point[i]=0.;
        weights[0]=1.-u-v-w; weights[1]=u; weights[2]=v; weights[3]=w; return 1;
    }
    const int faces[4][3]={{0,1,2},{0,1,3},{0,2,3},{1,2,3}};
    double best=INFINITY;
    for (int k=0;k<4;++k) {
        double candidate[3],local[3];
        if (!wheel_triangle(shape,vertices[faces[k][0]].point,vertices[faces[k][1]].point,
                            vertices[faces[k][2]].point,candidate,local)) return 0;
        double squared=dot(candidate,candidate);
        if (k==0 || squared<best) {
            best=squared;
            for (int i=0;i<3;++i) point[i]=candidate[i];
            for (int i=0;i<4;++i) weights[i]=0.;
            for (int i=0;i<3;++i) weights[faces[k][i]]=local[i];
        }
    }
    return 1;
}

typedef struct { double length,a[3],ab[3],ac[3],normal[3]; } WheelFace;
static int wheel_face_greater(WheelFace *a,WheelFace *b) {
    if (a->length!=b->length) return a->length>b->length;
    double *left[4]={a->a,a->ab,a->ac,a->normal},*right[4]={b->a,b->ab,b->ac,b->normal};
    for (int k=0;k<4;++k) for (int i=0;i<3;++i)
        if (left[k][i]!=right[k][i]) return left[k][i]>right[k][i];
    return 0;
}

static int wheel_accept(WheelConvex *shape,double distance,double normal[3],double point[3],WheelVertex *candidate) {
    for (int i=0;i<3;++i) point[i]=distance*normal[i];
    if (!wheel_support(shape,point,candidate)) return -1;
    double squared=dot(point,point);
    return squared-dot(point,candidate->point)<=1e-13*fmax(1.,squared);
}

static int wheel_faces(WheelConvex *shape,double bodies[4][3],int count,
                       double *distance,double normal[3],double witness[3]) {
    WheelFace faces[4]; int n=0;
    for (int i=0;i<count-2;++i) for (int j=i+1;j<count-1;++j) for (int k=j+1;k<count;++k) {
        WheelFace face;
        for (int a=0;a<3;++a) face.a[a]=bodies[i][a];
        subtract(bodies[j],bodies[i],face.ab); subtract(bodies[k],bodies[i],face.ac);
        cross_precise(face.ab,face.ac,face.normal); face.length=sqrt(exact_dot(face.normal,face.normal));
        if (face.length!=0.) faces[n++]=face;
    }
    for (int i=1;i<n;++i) {
        WheelFace face=faces[i]; int j=i;
        while (j>0 && wheel_face_greater(&face,&faces[j-1])) { faces[j]=faces[j-1]; --j; }
        faces[j]=face;
    }
    for (int k=0;k<n;++k) {
        WheelFace *face=&faces[k]; double terms[3],negative[3],offset[3],relative[3],rhs[3];
        for (int i=0;i<3;++i) { normal[i]=face->normal[i]/face->length; terms[i]=normal[i]*(shape->center[i]-face->a[i]); }
        if (sum_four((double[4]){terms[0],terms[1],terms[2],0.})<0.)
            for (int i=0;i<3;++i) normal[i]=-normal[i];
        for (int i=0;i<3;++i) negative[i]=-normal[i];
        if (!support_values(negative,shape->axis,shape->radius,shape->half,0.,shape->crown,offset)) return -1;
        for (int i=0;i<3;++i) {
            relative[i]=sum_four((double[4]){shape->center[i],-face->a[i],offset[i],0.});
            terms[i]=normal[i]*relative[i];
        }
        *distance=sum_four((double[4]){terms[0],terms[1],terms[2],0.});
        if (*distance<=0.) continue;
        for (int i=0;i<3;++i) rhs[i]=relative[i]- *distance*normal[i];
        double columns[3][3],values[3]; int rank;
        for (int i=0;i<3;++i) { columns[0][i]=face->ab[i]; columns[1][i]=face->ac[i]; }
        if (!wheel_coordinates(shape,columns,2,rhs,values,&rank)) return -1;
        double v=values[0],w=values[1];
        if (rank==2 && v>=0. && w>=0. && v+w<=1.) {
            double point[3]; WheelVertex candidate;
            int accepted=wheel_accept(shape,*distance,normal,point,&candidate);
            if (accepted<0) return -1;
            if (accepted) {
                for (int i=0;i<3;++i) witness[i]=sum_four((double[4]){face->a[i],v*face->ab[i],w*face->ac[i],0.});
                return 1;
            }
        }
    }
    return 0;
}

static int wheel_bodies(WheelVertex vertices[4],double weights[4],int count,int positive,double bodies[4][3]) {
    int n=0;
    for (int k=0;k<count;++k) {
        if (positive && weights[k]<=0.) continue;
        int found=0;
        for (int i=0;i<n;++i) if (wheel_same(vertices[k].body,bodies[i])) found=1;
        if (!found) { for (int i=0;i<3;++i) bodies[n][i]=vertices[k].body[i]; ++n; }
    }
    return n;
}

static int wheel_convex_values(WheelConvex *shape,double *distance,double normal[3],double witness[3]) {
    double direction[3],body[3],point[3],weights[4];
    WheelVertex vertices[4]; int count=1;
    if (!wheel_body(shape,shape->center,body)) return 0;
    subtract(shape->center,body,direction);
    if (dot(direction,direction)==0.) { direction[0]=0.; direction[1]=0.; direction[2]=1.; }
    if (!wheel_support(shape,direction,&vertices[0]) || !wheel_closest(shape,vertices,count,point,weights)) return 0;
    for (int iteration=0;iteration<96;++iteration) {
        double squared=dot(point,point);
        if (squared<1e-24) {
            *distance=0.; normal[0]=0.; normal[1]=0.; normal[2]=1.;
            for (int i=0;i<3;++i) witness[i]=shape->center[i]; return 1;
        }
        double bodies[4][3]; int n=wheel_bodies(vertices,weights,count,1,bodies);
        if (n<=2) {
            if (!edge_distance_values(shape->center,shape->axis,bodies[0],bodies[n-1],shape->radius,shape->half,
                                      shape->crown,distance,normal,witness)) return 0;
            double refined[3]; WheelVertex candidate;
            int accepted=wheel_accept(shape,*distance,normal,refined,&candidate);
            if (accepted<0) return 0; if (accepted) return 1;
        }
        n=wheel_bodies(vertices,weights,count,0,bodies);
        if (n>=3) {
            int accepted=wheel_faces(shape,bodies,n,distance,normal,witness);
            if (accepted<0) return 0; if (accepted) return 1;
        }
        WheelVertex candidate;
        if (!wheel_support(shape,point,&candidate)) return 0;
        if (squared-dot(point,candidate.point)<=1e-13*fmax(1.,squared)) {
            n=wheel_bodies(vertices,weights,count,1,bodies);
            if (n<=2) {
                if (!edge_distance_values(shape->center,shape->axis,bodies[0],bodies[n-1],shape->radius,shape->half,
                                          shape->crown,distance,normal,witness)) return 0;
                double refined[3]; int accepted=wheel_accept(shape,*distance,normal,refined,&candidate);
                if (accepted<0) return 0; if (accepted) return 1;
                for (int i=0;i<3;++i) { vertices[0].point[i]=refined[i]; vertices[0].body[i]=witness[i]; }
                vertices[1]=candidate; count=2;
                if (!wheel_closest(shape,vertices,count,point,weights)) return 0;
                continue;
            }
            *distance=sqrt(squared);
            for (int i=0;i<3;++i) {
                double terms[4]; for (int k=0;k<count;++k) terms[k]=weights[k]*vertices[k].body[i];
                witness[i]=sum_values(terms,count); normal[i]=point[i]/ *distance;
            }
            return 1;
        }
        int write=0;
        for (int k=0;k<count;++k) if (weights[k]>1e-15) vertices[write++]=vertices[k];
        if (write>=4) { PyErr_SetString(PyExc_ArithmeticError,"轮胎凸体单纯形未缩减"); return 0; }
        vertices[write++]=candidate; count=write;
        if (!wheel_closest(shape,vertices,count,point,weights)) return 0;
    }
    PyErr_SetString(PyExc_ArithmeticError,"圆柱/固定凸体距离未收敛"); return 0;
}

static PyObject *convex_distance_call(PyObject *self,PyObject *args) {
    PyObject *center,*axis,*body,*coordinates; int kind;
    double radius,half,shoulder,crown;
    if (!PyArg_ParseTuple(args,"OOOddddOi",&center,&axis,&body,&radius,&half,&shoulder,&crown,&coordinates,&kind)) return NULL;
    WheelConvex shape={0};
    if (!vector(center,shape.center) || !vector(axis,shape.axis)) return NULL;
    shape.radius=radius-shoulder; shape.half=half-shoulder; shape.crown=crown; shape.coordinates=coordinates;
    PyObject *sequence=NULL;
    if (kind==0) shape.support=body;
    else if (kind==1) { if (!vector(body,shape.box)) return NULL; }
    else {
        sequence=PySequence_Fast(body,"凸体顶点须为序列");
        if (!sequence) return NULL;
        shape.count=PySequence_Fast_GET_SIZE(sequence);
        if (!shape.count) { Py_DECREF(sequence); PyErr_SetString(PyExc_ValueError,"凸体顶点不能为空"); return NULL; }
        shape.polygon=PyMem_Malloc(shape.count*sizeof(*shape.polygon));
        if (!shape.polygon) { Py_DECREF(sequence); return PyErr_NoMemory(); }
        for (Py_ssize_t i=0;i<shape.count;++i) if (!vector(PySequence_Fast_GET_ITEM(sequence,i),shape.polygon[i])) goto error;
    }
    double distance,normal[3],witness[3];
    if (!wheel_convex_values(&shape,&distance,normal,witness)) goto error;
    PyMem_Free(shape.polygon); Py_XDECREF(sequence);
    return Py_BuildValue("(d(ddd)(ddd))",distance,normal[0],normal[1],normal[2],witness[0],witness[1],witness[2]);
error:
    PyMem_Free(shape.polygon); Py_XDECREF(sequence); return NULL;
}
