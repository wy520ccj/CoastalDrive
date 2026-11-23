#version 330
uniform sampler3D cloud_noise;
uniform vec4 tile_rect;
uniform vec3 sun_direction;
uniform int trace_steps;
in vec2 uv;
out vec4 fragColor;

// 公里制离线薄云层；驾驶时只读取烘焙结果，不执行体积追踪。
const float planet_radius=6371.;
const float cloud_base=1.45;
const float cloud_top=1.95;
const float extinction=7.5;

float cloud_density(vec3 p) {
    float height=p.z+dot(p.xy,p.xy)/(2.*planet_radius);
    float h=(height-cloud_base)/(cloud_top-cloud_base);
    if (h<=0. || h>=1.) return 0.;
    vec4 n=textureLod(cloud_noise,p/4.6,0.);
    float weather=textureLod(cloud_noise,vec3(p.xy/48.,.37),0.).r;
    float shape=dot(n.gba,vec3(.65,.25,.10));
    float threshold=.49+.08*(1.-weather);
    float envelope=smoothstep(0.,.17,h)*(1.-smoothstep(.45,1.,h));
    float density=max(0.,(shape-threshold)*14.)*envelope;
    float erosion=textureLod(cloud_noise,p/.9,0.).a*.18;
    return max(0.,density-erosion)*.9;
}

float layer_distance(vec3 ray,float height) {
    // 抛物曲率避免大半径平方相减，海平线附近仍保持连续。
    float horizontal=dot(ray.xy,ray.xy);
    return 2.*height/(ray.z+sqrt(ray.z*ray.z+2.*height*horizontal/planet_radius));
}

vec3 clear_sky(vec3 ray) {
    float altitude=max(ray.z,0.);
    vec3 zenith=vec3(.95,1.38,1.96);
    float towards_sun=pow(max(dot(normalize(ray.xy),normalize(sun_direction.xy)),0.),5.);
    vec3 horizon=mix(vec3(2.3,2.55,2.8),vec3(6.3,3.35,1.2),towards_sun);
    vec3 color=mix(zenith,horizon,exp(-altitude*11.));
    float angle=acos(clamp(dot(ray,sun_direction),-1.,1.));
    float disk=1.-smoothstep(radians(.255),radians(.28),angle);
    color+=vec3(160.,112.,48.)*disk;
    color+=vec3(3.1,1.8,.65)*exp(-pow(angle/radians(3.1),2.));
    return color;
}

void main() {
    vec2 full_uv=tile_rect.xy+uv*tile_rect.zw;
    float longitude=full_uv.x*6.283185307;
    float latitude=(full_uv.y-.5)*3.141592654;
    vec3 ray=vec3(cos(latitude)*cos(longitude),cos(latitude)*sin(longitude),sin(latitude));
    vec3 background=clear_sky(ray);
    if (ray.z<.002) {
        fragColor=vec4(background,1.);
        return;
    }
    float near_distance=layer_distance(ray,cloud_base);
    float far_distance=min(layer_distance(ray,cloud_top),90.);
    float step_size=(far_distance-near_distance)/float(trace_steps);
    float transmittance=1.;
    vec3 scattered=vec3(0.);
    float g=.35;
    float phase=(1.-g*g)/(12.566370614*pow(1.+g*g-2.*g*dot(ray,sun_direction),1.5));
    for (int i=0;i<trace_steps;i++) {
        if (transmittance<.008) break;
        vec3 p=ray*(near_distance+(float(i)+.5)*step_size);
        float density=cloud_density(p);
        if (density<.001) continue;
        float shadow=0.;
        for (int j=0;j<16;j++) {
            shadow+=cloud_density(p+sun_direction*(float(j)+.5)*.15)*.15;
        }
        float sunlight=exp(-shadow*extinction);
        float height=clamp((p.z+dot(p.xy,p.xy)/(2.*planet_radius)-cloud_base)/(cloud_top-cloud_base),0.,1.);
        vec3 ambient=vec3(.50,.70,1.10)*(.65+.35*height);
        vec3 lighting=ambient+vec3(7.1,3.5,.95)*sunlight*(.55+phase*2.2);
        lighting=mix(lighting,background,1.-exp(-length(p)/80.));
        float opacity=1.-exp(-density*step_size*extinction);
        scattered+=transmittance*lighting*opacity;
        transmittance*=1.-opacity;
    }
    fragColor=vec4(scattered+background*transmittance,1.);
}
