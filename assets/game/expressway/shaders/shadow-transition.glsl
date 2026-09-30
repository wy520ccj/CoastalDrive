// 草地、山面和植被在实时阴影覆盖边缘渐变，避免树影随玩家靠近突然出现。
float shadow_caster_contrib(sampler2DShadow shadowmap, vec4 shadowpos) {
    vec3 p = shadowpos.xyz / shadowpos.w;
    vec3 edge = min(p, vec3(1.0) - p);
    float coverage = smoothstep(0.0, 0.20, min(edge.x, edge.y))
                   * smoothstep(0.0, 0.02, edge.z);
    if (coverage <= 0.0) return 1.0;
    p.z -= global_shadow_bias;
    return mix(1.0, texture(shadowmap, p), coverage);
}
