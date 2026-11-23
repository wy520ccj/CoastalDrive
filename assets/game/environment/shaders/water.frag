#version 330
uniform float sea_time;
uniform sampler2D shore_distance;
uniform sampler2D wave_normals;
uniform samplerCube filtered_env_map;
uniform vec3 camera_world_position;
uniform vec3 coastal_sun_direction;
uniform vec3 coastal_sun_color;
in vec3 world;
out vec4 fragColor;
void main() {
    vec2 p = world.xy;
    vec2 shore_uv = (p+256.)/640.;
    float coast = texture(shore_distance,shore_uv).r*40.;
    if (any(lessThan(shore_uv,vec2(0.))) || any(greaterThan(shore_uv,vec2(1.)))) coast=40.;
    float wash=.35*sin(p.x*.67+p.y*.43+sea_time*.7);
    float foam=(1.-smoothstep(.65,2.3,coast+wash))*(.65+.35*sin(p.x*1.9+p.y*1.7));
    // 多尺度风浪事先烘焙，自动mip过滤远处细浪；不在每像素叠加大量正弦。
    vec3 first=texture(wave_normals,p/64.+sea_time*vec2(.003,.001)).rgb*2.-1.;
    vec3 second=texture(wave_normals,vec2(-p.y,p.x)/28.+sea_time*vec2(-.002,.003)).rgb*2.-1.;
    vec3 normal=normalize(vec3(first.xy+vec2(second.y,-second.x)*.42,first.z));
    vec3 view=normalize(camera_world_position-world);
    float nv=max(dot(normal,view),.001);
    vec3 sky=textureLod(filtered_env_map,reflect(-view,normal),.35).rgb;
    float fresnel=.02+.98*pow(1.-nv,5.);
    vec3 color=vec3(.009,.039,.068)*(1.-fresnel)+sky*fresnel*.35;
    // 同方向太阳的GGX高光被真实浪面打散，倒影不跟随屏幕或固定世界条带。
    vec3 light=coastal_sun_direction;
    vec3 half_vector=normalize(view+light);
    float nl=max(dot(normal,light),0.);
    float nh=max(dot(normal,half_vector),0.);
    float vh=max(dot(view,half_vector),0.);
    float roughness=.14+.18*(1.-length(first));
    float a2=pow(roughness,4.);
    float d=a2/(3.141592654*pow(nh*nh*(a2-1.)+1.,2.));
    float k=roughness*roughness*.5;
    float g=(nv/(nv*(1.-k)+k))*(nl/(nl*(1.-k)+k));
    float f=.02+.98*pow(1.-vh,5.);
    color+=coastal_sun_color*.65*d*g*f/(4.*nv+.0001);
    color+=foam*vec3(.14,.17,.18);
    fragColor=vec4(color,1.);
}
