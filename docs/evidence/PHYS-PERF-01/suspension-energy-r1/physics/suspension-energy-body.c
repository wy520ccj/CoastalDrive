/* 同一悬架势能、硬件梯度与离散能量账；保留原乘法/求和次序。 */
static void suspension_elastic_values(const double compression[4],const double rates[4],const double bars[2],
    const double stops[4],double travel,double *spring,double bar[2],double *stop,double force[4]) {
    double matrix[16]={0.},terms[4],excess[4];
    for (int i=0; i<4; ++i) {
        matrix[i*4+i]=rates[i];
        terms[i]=rates[i]*compression[i]*compression[i]/2;
        double bounded=compression[i]<travel ? compression[i] : travel;
        bounded=bounded>-travel ? bounded : -travel;
        excess[i]=compression[i]-bounded;
    }
    *spring=compensated(terms,4);
    for (int axle=0; axle<2; ++axle) {
        int left=2*axle,right=left+1;
        matrix[left*4+left]+=bars[axle]; matrix[right*4+right]+=bars[axle];
        matrix[left*4+right]-=bars[axle]; matrix[right*4+left]-=bars[axle];
        bar[axle]=bars[axle]*pow(compression[left]-compression[right],2.)/2;
    }
    for (int i=0; i<4; ++i) terms[i]=stops[i]*excess[i]*excess[i]/2;
    *stop=compensated(terms,4);
    for (int i=0; i<4; ++i) {
        for (int j=0; j<4; ++j) terms[j]=matrix[i*4+j]*compression[j];
        force[i]=compensated(terms,4)+stops[i]*excess[i];
    }
}
static PyObject *suspension_elastic_terms(PyObject *self,PyObject *args) {
    PyObject *compression_object,*rates_object,*bars_object,*stops_object;
    double travel,compression[4],rates[4],bars[2],stops[4],spring,bar[2],stop,force[4];
    if (!PyArg_ParseTuple(args,"OOOOd",&compression_object,&rates_object,&bars_object,&stops_object,&travel)) return NULL;
    if (!vector(compression_object,compression,4) || !vector(rates_object,rates,4)
        || !vector(bars_object,bars,2) || !vector(stops_object,stops,4)) return NULL;
    suspension_elastic_values(compression,rates,bars,stops,travel,&spring,bar,&stop,force);
    return Py_BuildValue("(d(dd)d(dddd))",spring,bar[0],bar[1],stop,force[0],force[1],force[2],force[3]);
}
static PyObject *suspension_energy_account(PyObject *self,PyObject *args) {
    PyObject *compression_object,*speed_object,*mobility_object,*geometry_object,*end_object,*forces_object;
    PyObject *rates_object,*bars_object,*stops_object,*damping_object;
    double dt,travel,compression[4],speed[4],mobility[16],geometry[4],end[4],forces[4],rates[4],bars[2],stops[4],damping[4];
    if (!PyArg_ParseTuple(args,"OOOdOOOOOOdO",&compression_object,&speed_object,&mobility_object,&dt,
        &geometry_object,&end_object,&forces_object,&rates_object,&bars_object,&stops_object,&travel,&damping_object)) return NULL;
    if (!vector(compression_object,compression,4) || !vector(speed_object,speed,4)
        || !matrix_values(mobility_object,mobility,4,4) || !vector(geometry_object,geometry,4)
        || !vector(end_object,end,4) || !vector(forces_object,forces,4) || !vector(rates_object,rates,4)
        || !vector(bars_object,bars,2) || !vector(stops_object,stops,4) || !vector(damping_object,damping,4)) return NULL;
    double delta[4],rate[4],initial_spring,initial_bar[2],initial_stop,initial_force[4],spring,bar[2],stop,elastic_force[4],terms[4];
    for (int i=0; i<4; ++i) {delta[i]=end[i]-compression[i]; rate[i]=delta[i]/dt;}
    suspension_elastic_values(compression,rates,bars,stops,travel,&initial_spring,initial_bar,&initial_stop,initial_force);
    suspension_elastic_values(end,rates,bars,stops,travel,&spring,bar,&stop,elastic_force);
    double energy_change=spring+compensated(bar,2)+stop-initial_spring-compensated(initial_bar,2)-initial_stop;
    for (int i=0; i<4; ++i) terms[i]=damping[i]*delta[i]*delta[i]/dt;
    double damping_loss=compensated(terms,4);
    for (int i=0; i<4; ++i) terms[i]=elastic_force[i]*delta[i];
    double elastic_loss=compensated(terms,4)-energy_change;
    for (int i=0; i<4; ++i) {
        double row[4];
        for (int j=0; j<4; ++j) row[j]=mobility[i*4+j]*forces[j];
        terms[i]=forces[i]*compensated(row,4);
    }
    double body_loss=dt*dt*compensated(terms,4)/2;
    for (int i=0; i<4; ++i) terms[i]=forces[i]*(geometry[i]-compression[i]);
    double offset_work=compensated(terms,4);
    for (int i=0; i<4; ++i) terms[i]=forces[i]*speed[i];
    double kinetic_change=dt*compensated(terms,4)+body_loss;
    double residual=kinetic_change+energy_change+damping_loss+elastic_loss+body_loss-offset_work;
    return Py_BuildValue("((dddd)d(dd)ddddddd)",rate[0],rate[1],rate[2],rate[3],spring,bar[0],bar[1],
        stop,damping_loss,elastic_loss,body_loss,offset_work,residual,kinetic_change+body_loss);
}
