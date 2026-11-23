// 按接收面在阴影纹素中心的深度分别比较，保留原偏移和双线性权重。
float shadow_caster_contrib(sampler2DShadow shadowmap, vec4 shadowpos) {
    vec3 p = shadowpos.xyz / shadowpos.w;
    vec3 dx = dFdx(p), dy = dFdy(p);
    float determinant = dx.x*dy.y-dx.y*dy.x;
    vec2 slope = vec2(0.);
    if (abs(determinant) > 1e-20) {
        slope = vec2(dy.y*dx.z-dx.y*dy.z, dx.x*dy.z-dy.x*dx.z)/determinant;
    }
    vec3 edge = min(p, vec3(1.)-p);
    float coverage = smoothstep(0.,.20,min(edge.x,edge.y))*smoothstep(0.,.02,edge.z);
    if (coverage <= 0.) return 1.;
    vec2 size = vec2(textureSize(shadowmap,0));
    vec2 cell = p.xy*size-.5;
    vec2 first = floor(cell), fraction = fract(cell);
    float filtered = 0.;
    for (int y=0; y<2; ++y) for (int x=0; x<2; ++x) {
        vec2 uv = (first+vec2(x,y)+.5)/size;
        vec2 weight = mix(vec2(1.)-fraction,fraction,vec2(x,y));
        float depth = p.z+dot(uv-p.xy,slope)-global_shadow_bias;
        filtered += weight.x*weight.y*texture(shadowmap,vec3(uv,depth));
    }
    return mix(1.,filtered,coverage);
}
