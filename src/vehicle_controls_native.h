/* 原电子控制数值与完整冻结记录；不施力、不积分、不改变阈值或执行顺序。 */
enum {C_ABS,C_TCS,C_RESPONSE,C_TARGET,C_HYSTERESIS,C_MIN_SPEED,C_RELEASE,C_APPLY,C_RATE_GAIN,
      C_SLIP_SPEED,C_PREDICTION,C_BRAKE_GAIN,C_MAX_BRAKE,C_SCALE,C_ACTIVE,C_SLIPS,C_OMEGA,C_RADIUS,
      C_SPEED,C_SUPPORT,C_TICK,C_COMMAND,C_PRESSURE,C_BRAKING_SLIP,C_ABS_ACTIVE,
      C_REQUESTED,C_PHASE,C_PREDICTED,C_PEDAL,C_REQUESTS,C_TICKS,C_ESC,C_REFERENCE_RESPONSE,C_YAW_GAIN,
      C_BETA_GAIN,C_YAW_THRESHOLD,C_BETA_THRESHOLD,C_MOMENT_THRESHOLD,C_CUT_GAIN,C_CONTINUOUS,
      C_REFERENCE,C_UNLIMITED,C_YAW,C_BETA,C_YAW_ERROR,C_TARGET_MOMENT,C_BASELINE,C_ALLOCATED,C_RESIDUAL,
      C_REFERENCE_BETA,C_BETA_ERROR,C_MASS,C_WHEELBASE,C_FRONT_WEIGHT,C_REAR_STIFFNESS,
      C_NORMAL,C_RELEASE_PHASE,C_APPLY_PHASE,C_HOLD_PHASE,C_KEY_COUNT};
static PyObject *control_keys[C_KEY_COUNT];
static int control_keys_init(void) {
    const char *names[]={"abs_enabled","tcs_enabled","response_time","target_slip","slip_hysteresis","minimum_speed",
        "release_rate","apply_rate","slip_rate_gain","slip_speed","prediction_time","brake_gain","maximum_brake",
        "torque_scale","active","wheel_slips","omega","rolling_radius","longitudinal_speed","sample_support","sample_tick",
        "commanded","pressure","braking_slip","abs_active","requested","phase","predicted_slip","requested_throttle",
        "brake_requests","feedback_ticks","esc_enabled","reference_response","yaw_gain","sideslip_gain","yaw_threshold",
        "sideslip_threshold","moment_threshold","engine_cut_gain","continuous_reference","reference_yaw_rate",
        "unlimited_yaw_rate","observed_yaw_rate","sideslip","yaw_error","desired_brake_moment","baseline_brake_moment",
        "allocated_brake_moment","residual_moment","reference_sideslip","sideslip_error","mass","wheelbase",
        "front_weight_share","rear_lateral_stiffness","normal","release","apply","hold"};
    for(int i=0;i<C_KEY_COUNT;++i){control_keys[i]=PyUnicode_InternFromString(names[i]);if(!control_keys[i]){
        for(int j=0;j<i;++j)Py_CLEAR(control_keys[j]);return 0;}}
    return 1;
}
static PyObject *control_field(PyObject *dict,int key) {
    PyObject *value=PyDict_GetItemWithError(dict,control_keys[key]);
    if(!value&&!PyErr_Occurred())PyErr_SetObject(PyExc_KeyError,control_keys[key]);return value;
}
static int control_number(PyObject *dict,int key,double *value) {
    PyObject *item=control_field(dict,key);if(!item)return 0;*value=PyFloat_AsDouble(item);return !PyErr_Occurred();
}
static int control_bool(PyObject *dict,int key) {
    PyObject *item=control_field(dict,key);return item?PyObject_IsTrue(item):-1;
}
static double control_min(double a,double b){return b<a?b:a;}
static double control_max(double a,double b){return b>a?b:a;}
static int control_put(PyObject *dict,int key,PyObject *value) {
    return PyDict_SetItem(dict,control_keys[key],value)==0;
}
static int control_float(PyObject *dict,int key,double value) {
    PyObject *number=PyFloat_FromDouble(value);if(!number)return 0;
    int ok=control_put(dict,key,number);Py_DECREF(number);return ok;
}
static PyObject *control_record(PyObject *previous,PyObject *updates) {
    PyObject *arguments=PyTuple_Pack(1,previous);if(!arguments)return NULL;
    PyObject *record=wheel_state_update(NULL,arguments,updates);Py_DECREF(arguments);return record;
}
static int control_four(PyObject *value) {
    if(!PyTuple_Check(value)||PyTuple_GET_SIZE(value)!=4){PyErr_SetString(PyExc_ValueError,"电子控制须有四轮反馈");return 0;}
    return 1;
}

static PyObject *brakes_advance_native(PyObject *self,PyObject *args) {
    PyObject *config,*previous,*wheels,*requests;double radius,dt;
    if(!PyArg_ParseTuple(args,"OOOOdd",&config,&previous,&wheels,&requests,&radius,&dt))return NULL;
    if(!control_four(previous)||!control_four(wheels)||!control_four(requests))return NULL;
    PyObject *settings=PyObject_GenericGetDict(config,NULL),*states=PyTuple_New(4),*pressures=PyTuple_New(4);
    PyObject *wheel=NULL,*old=NULL,*updates=NULL,*command_object=NULL;
    if(!settings||!states||!pressures)goto failed;
    int abs_enabled=control_bool(settings,C_ABS);double response,target,hysteresis,minimum,release,apply,gain;
    if(abs_enabled<0||!control_number(settings,C_RESPONSE,&response)||!control_number(settings,C_TARGET,&target)
        ||!control_number(settings,C_HYSTERESIS,&hysteresis)||!control_number(settings,C_MIN_SPEED,&minimum)
        ||!control_number(settings,C_RELEASE,&release)||!control_number(settings,C_APPLY,&apply)
        ||!control_number(settings,C_RATE_GAIN,&gain))goto failed;
    for(int i=0;i<4;++i){wheel=PyObject_GenericGetDict(PyTuple_GET_ITEM(wheels,i),NULL);
        old=PyObject_GenericGetDict(PyTuple_GET_ITEM(previous,i),NULL);updates=PyDict_New();if(!wheel||!old||!updates)goto failed;
        PyObject *request_object=PyTuple_GET_ITEM(requests,i),*rolling=control_field(wheel,C_RADIUS);
        double request=PyFloat_AsDouble(request_object),vx,omega,pressure,old_command;
        int support=control_bool(wheel,C_SUPPORT),old_active=control_bool(old,C_ABS_ACTIVE);
        if(!rolling||support<0||old_active<0||PyErr_Occurred()||!control_number(wheel,C_SPEED,&vx)
            ||!control_number(wheel,C_OMEGA,&omega)||!control_number(old,C_PRESSURE,&pressure)
            ||!control_number(old,C_COMMAND,&old_command))goto failed;
        double wheel_radius=rolling==Py_None?radius:PyFloat_AsDouble(rolling);if(PyErr_Occurred())goto failed;
        double speed=fabs(vx),slip=0.,predicted=0.;int has_slip=support&&speed>=minimum;
        if(has_slip){if(speed==0.){PyErr_SetString(PyExc_ZeroDivisionError,"制动滑移速度为零");goto failed;}
            slip=(speed-copysign(1.,vx)*wheel_radius*omega)/speed;predicted=slip;
            PyObject *last=control_field(old,C_BRAKING_SLIP);if(!last)goto failed;
            if(last!=Py_None){if(dt==0.){PyErr_SetString(PyExc_ZeroDivisionError,"制动反馈时间步为零");goto failed;}
                double old_slip=PyFloat_AsDouble(last);if(PyErr_Occurred())goto failed;
                predicted+=response*(slip-old_slip)/dt;}}
        int active=abs_enabled&&request>0.&&support&&speed>=minimum&&(old_active||predicted>target+hysteresis);
        double command=request;int phase=C_NORMAL;
        command_object=Py_NewRef(request_object);
        if(active){command=control_min(old_command,request);Py_SETREF(command_object,Py_NewRef(
                request<old_command?request_object:control_field(old,C_COMMAND)));if(!command_object)goto failed;
            double error=target-predicted;
            if(error<-hysteresis){command=control_max(0.,command+control_max(-release,gain*error)*dt);phase=C_RELEASE_PHASE;
                Py_SETREF(command_object,PyFloat_FromDouble(command));if(!command_object)goto failed;}
            else if(error>hysteresis){double candidate=command+control_min(apply,gain*error)*dt;
                command=control_min(request,candidate);phase=C_APPLY_PHASE;
                Py_SETREF(command_object,candidate<request?PyFloat_FromDouble(command):Py_NewRef(request_object));if(!command_object)goto failed;}}
        PyObject *pressure_object=response==0.?Py_NewRef(command_object):PyFloat_FromDouble(
            pressure+(command-pressure)*(1-exp(-dt/response)));
        if(!pressure_object)goto failed;
        int ok=control_put(updates,C_REQUESTED,request_object)&&control_put(updates,C_COMMAND,command_object)
            &&control_put(updates,C_PRESSURE,pressure_object)&&control_put(updates,C_ABS_ACTIVE,active?Py_True:Py_False)
            &&control_put(updates,C_PHASE,control_keys[phase]);
        PyObject *tick=control_field(wheel,C_TICK);if(!tick)ok=0;else ok=ok&&PyDict_SetItemString(updates,"feedback_tick",tick)==0;
        ok=ok&&(has_slip?control_float(updates,C_BRAKING_SLIP,slip):control_put(updates,C_BRAKING_SLIP,Py_None))
            &&(has_slip?control_float(updates,C_PREDICTED,predicted):control_put(updates,C_PREDICTED,Py_None));
        if(!ok){Py_DECREF(pressure_object);goto failed;}
        PyObject *record=control_record(PyTuple_GET_ITEM(previous,i),updates);if(!record){Py_DECREF(pressure_object);goto failed;}
        PyTuple_SET_ITEM(states,i,record);PyTuple_SET_ITEM(pressures,i,pressure_object);
        Py_CLEAR(wheel);Py_CLEAR(old);Py_CLEAR(updates);Py_CLEAR(command_object);
    }
    Py_DECREF(settings);PyObject *result=PyTuple_Pack(2,states,pressures);Py_DECREF(states);Py_DECREF(pressures);return result;
failed:
    Py_XDECREF(settings);Py_XDECREF(states);Py_XDECREF(pressures);Py_XDECREF(wheel);Py_XDECREF(old);
    Py_XDECREF(updates);Py_XDECREF(command_object);return NULL;
}

static PyObject *traction_advance_native(PyObject *self,PyObject *args) {
    PyObject *config,*previous,*wheels,*driven,*pedal_object;double radius,dt,direction;int braking;
    if(!PyArg_ParseTuple(args,"OOOdpOOdd",&config,&previous,&pedal_object,&direction,&braking,&wheels,&driven,&radius,&dt))return NULL;
    if(!control_four(wheels)||!PyTuple_Check(driven)){if(!PyErr_Occurred())PyErr_SetString(PyExc_TypeError,"驱动轮须为元组");return NULL;}
    PyObject *settings=PyObject_GenericGetDict(config,NULL),*old=PyObject_GenericGetDict(previous,NULL);
    PyObject *slips=PyTuple_New(4),*ticks=PyTuple_New(4),*requests=NULL,*updates=NULL,*wheel=NULL;
    if(!settings||!old||!slips||!ticks)goto failed;
    double pedal=PyFloat_AsDouble(pedal_object),target,hysteresis,slip_speed,prediction,release,apply,gain,brake_gain,maximum;
    int enabled=control_bool(settings,C_TCS),last_active=control_bool(old,C_ACTIVE);
    if(enabled<0||last_active<0||PyErr_Occurred()||!control_number(settings,C_TARGET,&target)
        ||!control_number(settings,C_HYSTERESIS,&hysteresis)||!control_number(settings,C_SLIP_SPEED,&slip_speed)
        ||!control_number(settings,C_PREDICTION,&prediction)||!control_number(settings,C_RELEASE,&release)
        ||!control_number(settings,C_APPLY,&apply)||!control_number(settings,C_RATE_GAIN,&gain)
        ||!control_number(settings,C_BRAKE_GAIN,&brake_gain)||!control_number(settings,C_MAX_BRAKE,&maximum))goto failed;
    double values[4],commands[4]={0.};int supported[4];
    for(int i=0;i<4;++i){wheel=PyObject_GenericGetDict(PyTuple_GET_ITEM(wheels,i),NULL);if(!wheel)goto failed;
        supported[i]=control_bool(wheel,C_SUPPORT);PyObject *rolling=control_field(wheel,C_RADIUS),*tick=control_field(wheel,C_TICK);
        double vx,omega;if(supported[i]<0||!rolling||!tick||!control_number(wheel,C_SPEED,&vx)||!control_number(wheel,C_OMEGA,&omega))goto failed;
        double wheel_radius=rolling==Py_None?radius:PyFloat_AsDouble(rolling);if(PyErr_Occurred())goto failed;
        if(supported[i]){double divisor=control_max(fabs(vx),slip_speed);
            if(divisor==0.){PyErr_SetString(PyExc_ZeroDivisionError,"牵引滑移速度尺度为零");goto failed;}
            values[i]=direction*(wheel_radius*omega-vx)/divisor;PyTuple_SET_ITEM(slips,i,PyFloat_FromDouble(values[i]));}
        else PyTuple_SET_ITEM(slips,i,Py_NewRef(Py_None));
        if(!PyTuple_GET_ITEM(slips,i))goto failed;PyTuple_SET_ITEM(ticks,i,Py_NewRef(tick));Py_CLEAR(wheel);}
    double scale=1.,worst=0.;int active=0,found=0,eligible=enabled&&pedal>0.&&direction!=0.&&!braking;
    PyObject *last_slips=control_field(old,C_SLIPS);if(!last_slips||!control_four(last_slips))goto failed;
    if(eligible){for(Py_ssize_t j=0;j<PyTuple_GET_SIZE(driven);++j){long i=PyLong_AsLong(PyTuple_GET_ITEM(driven,j));
            if(PyErr_Occurred())goto failed;if(i<0||i>=4){PyErr_SetString(PyExc_IndexError,"驱动轮索引越界");goto failed;}
            if(!supported[i])continue;double trend=0.;PyObject *last=PyTuple_GET_ITEM(last_slips,i);
            if(last!=Py_None){if(dt==0.){PyErr_SetString(PyExc_ZeroDivisionError,"牵引反馈时间步为零");goto failed;}
                double old_slip=PyFloat_AsDouble(last);if(PyErr_Occurred())goto failed;trend=(values[i]-old_slip)/dt;}
            double predicted=values[i]+prediction*trend;if(!found||predicted>worst)worst=predicted;found=1;
            commands[i]=control_min(maximum,brake_gain*control_max(0.,values[i]-target));}
        if(found){active=last_active||worst>target+hysteresis;
            if(active){double old_scale;if(!control_number(old,C_SCALE,&old_scale))goto failed;
                double rate=control_max(-release,control_min(apply,gain*(target-worst)));
                scale=control_max(0.,control_min(1.,old_scale+rate*dt));
                active=scale<1.||commands[0]!=0.||commands[1]!=0.||commands[2]!=0.||commands[3]!=0.;}
            else memset(commands,0,sizeof(commands));}}
    requests=Py_BuildValue("(dddd)",commands[0],commands[1],commands[2],commands[3]);updates=PyDict_New();if(!requests||!updates)goto failed;
    if(!control_put(updates,C_PEDAL,pedal_object)||!control_float(updates,C_SCALE,scale)||!control_put(updates,C_ACTIVE,active?Py_True:Py_False)
        ||!control_put(updates,C_SLIPS,slips)||!control_put(updates,C_REQUESTS,requests)||!control_put(updates,C_TICKS,ticks))goto failed;
    PyObject *result=control_record(previous,updates);Py_DECREF(settings);Py_DECREF(old);Py_DECREF(slips);Py_DECREF(ticks);
    Py_DECREF(requests);Py_DECREF(updates);return result;
failed:
    Py_XDECREF(settings);Py_XDECREF(old);Py_XDECREF(slips);Py_XDECREF(ticks);Py_XDECREF(requests);Py_XDECREF(updates);Py_XDECREF(wheel);return NULL;
}

static double control_sum4(const double values[4]) {
    double sum=0.,correction=0.;for(int i=0;i<4;++i){double next=sum+values[i];
        correction+=fabs(sum)>=fabs(values[i])?(sum-next)+values[i]:(values[i]-next)+sum;sum=next;}
    return correction!=0.&&isfinite(correction)?sum+correction:sum;
}
static double control_excess(double value,double threshold) {
    return copysign(control_max(0.,fabs(value)-threshold),value);
}

static PyObject *stability_advance_native(PyObject *self,PyObject *args) {
    PyObject *config,*vehicle,*previous,*requests,*capacities_object,*limits_object,*arms_object,*tick;
    double speed,yaw,beta,inertia,steering,dt,grip_budget;int supported;
    if(!PyArg_ParseTuple(args,"OOOOddddddOOOdpO",&config,&vehicle,&previous,&requests,&speed,&yaw,&beta,&inertia,
        &steering,&dt,&capacities_object,&limits_object,&arms_object,&grip_budget,&supported,&tick))return NULL;
    if(!control_four(requests)||!control_four(capacities_object)||!control_four(limits_object)||!control_four(arms_object))return NULL;
    PyObject *settings=PyObject_GenericGetDict(config,NULL),*hardware=PyObject_GenericGetDict(vehicle,NULL);
    PyObject *old=PyObject_GenericGetDict(previous,NULL),*output=NULL,*updates=NULL;
    if(!settings||!hardware||!old)goto failed;
    int enabled=control_bool(settings,C_ESC),continuous=control_bool(settings,C_CONTINUOUS);
    double minimum,response,yaw_gain,beta_gain,yaw_threshold,beta_threshold,moment_threshold,cut_gain;
    double mass,wheelbase,front_weight,rear_stiffness;
    if(enabled<0||continuous<0||!control_number(settings,C_MIN_SPEED,&minimum)||!control_number(settings,C_REFERENCE_RESPONSE,&response)
        ||!control_number(settings,C_YAW_GAIN,&yaw_gain)||!control_number(settings,C_BETA_GAIN,&beta_gain)
        ||!control_number(settings,C_YAW_THRESHOLD,&yaw_threshold)||!control_number(settings,C_BETA_THRESHOLD,&beta_threshold)
        ||!control_number(settings,C_MOMENT_THRESHOLD,&moment_threshold)||!control_number(settings,C_CUT_GAIN,&cut_gain)
        ||!control_number(hardware,C_MASS,&mass)||!control_number(hardware,C_WHEELBASE,&wheelbase)
        ||!control_number(hardware,C_FRONT_WEIGHT,&front_weight)||!control_number(hardware,C_REAR_STIFFNESS,&rear_stiffness))goto failed;
    double capacities[4],limits[4],arms[4],commands[4],base[4],terms[4];
    for(int i=0;i<4;++i){capacities[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(capacities_object,i));
        limits[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(limits_object,i));arms[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(arms_object,i));
        commands[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(requests,i));if(PyErr_Occurred())goto failed;
        base[i]=control_min(commands[i]*capacities[i],limits[i]);terms[i]=base[i]*arms[i];}
    double baseline=control_sum4(terms),direction=copysign(1.,speed);
    if(wheelbase==0.){PyErr_SetString(PyExc_ZeroDivisionError,"稳定参考轴距为零");goto failed;}
    double unlimited=-speed*tan(steering*(3.141592653589793/180.))/wheelbase;
    int eligible=fabs(speed)>=minimum&&supported;
    double reference=0.,reference_beta=0.,target=0.,scale=1.,allocated=baseline;
    if(eligible||(continuous&&supported&&speed!=0.)){
        if(mass*fabs(speed)==0.||response==0.||rear_stiffness==0.){
            PyErr_SetString(PyExc_ZeroDivisionError,"稳定参考速度/质量/响应或侧偏刚度为零");goto failed;}
        double yaw_limit=grip_budget/(mass*fabs(speed));
        double achievable=control_max(-yaw_limit,control_min(yaw_limit,unlimited)),last;
        if(!control_number(old,C_REFERENCE,&last))goto failed;
        reference=last+(achievable-last)*(1-exp(-dt/response));
        double rear_distance=wheelbase*front_weight;
        double rear_slip=mass*front_weight*speed*reference/(2*rear_stiffness);
        reference_beta=atan(-rear_distance*reference/fabs(speed)+rear_slip);
    }
    if(eligible)target=inertia*(yaw_gain*control_excess(reference-yaw,yaw_threshold)
        -direction*beta_gain*control_excess(beta-reference_beta,beta_threshold));
    output=Py_NewRef(requests);
    if(enabled&&eligible&&fabs(target-baseline)>moment_threshold){double forces[4];memcpy(forces,base,sizeof(base));
        double remaining=target-baseline,sign=copysign(1.,remaining);
        for(int i=0;i<4;++i)if(arms[i]*sign<0.){double release=control_min(forces[i],fabs(remaining/arms[i]));
            forces[i]-=release;remaining+=release*arms[i];}
        int rear=fabs(yaw)<fabs(reference)&&yaw*reference>=0.;const int orders[2][4]={{0,1,2,3},{2,3,0,1}};
        for(int j=0;j<4;++j){int i=orders[rear][j];if(arms[i]*sign>0.){
            double apply=control_min(limits[i]-forces[i],fabs(remaining/arms[i]));forces[i]+=apply;remaining-=apply*arms[i];}}
        Py_SETREF(output,PyTuple_New(4));if(!output)goto failed;
        for(int i=0;i<4;++i){PyObject *value;
            if(forces[i]==base[i])value=Py_NewRef(PyTuple_GET_ITEM(requests,i));
            else {if(capacities[i]==0.){PyErr_SetString(PyExc_ZeroDivisionError,"分轮稳定制动容量为零");goto failed;}
                value=PyFloat_FromDouble(forces[i]/capacities[i]);}
            if(!value)goto failed;PyTuple_SET_ITEM(output,i,value);terms[i]=forces[i]*arms[i];}
        allocated=control_sum4(terms);
        if(yaw_threshold==0.||beta_threshold==0.){PyErr_SetString(PyExc_ZeroDivisionError,"稳定误差阈值为零");goto failed;}
        scale=control_max(0.,1-cut_gain*(fabs(control_excess(reference-yaw,yaw_threshold))/yaw_threshold
            +fabs(control_excess(beta-reference_beta,beta_threshold))/beta_threshold));
    }
    int active=PyObject_RichCompareBool(output,requests,Py_NE);if(active<0)goto failed;active=active||scale<1.;
    updates=PyDict_New();if(!updates)goto failed;
    const int fields[]={C_REFERENCE,C_UNLIMITED,C_YAW,C_BETA,C_YAW_ERROR,C_TARGET_MOMENT,C_BASELINE,C_ALLOCATED,
        C_RESIDUAL,C_SCALE,C_REFERENCE_BETA,C_BETA_ERROR};
    const double values[]={reference,unlimited,yaw,beta,reference-yaw,target,baseline,allocated,target-allocated,
        scale,reference_beta,beta-reference_beta};
    for(int i=0;i<12;++i)if(!control_float(updates,fields[i],values[i]))goto failed;
    if(!control_put(updates,C_REQUESTS,output)||!control_put(updates,C_ACTIVE,active?Py_True:Py_False)
        ||PyDict_SetItemString(updates,"feedback_tick",tick)<0)goto failed;
    PyObject *result=control_record(previous,updates);Py_DECREF(settings);Py_DECREF(hardware);Py_DECREF(old);Py_DECREF(output);Py_DECREF(updates);return result;
failed:
    Py_XDECREF(settings);Py_XDECREF(hardware);Py_XDECREF(old);Py_XDECREF(output);Py_XDECREF(updates);return NULL;
}
