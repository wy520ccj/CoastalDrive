// 固定太阳下连续护栏的遮蔽坐标随道路几何保存，与相机和阴影图范围无关。
in vec2 v_rail_shadow_coord;
float expressway_rail_shadow() {
    float d = v_rail_shadow_coord.x;
    float reach = v_rail_shadow_coord.y;
    float softness = max(0.025, fwidth(d));
    float coverage = 0.0;
    for (int side = -1; side <= 1; side += 2) {
        float lo = float(side) * 8.0 - 0.12 + min(0.0, reach);
        float hi = float(side) * 8.0 + 0.12 + max(0.0, reach);
        coverage = max(coverage, smoothstep(lo-softness, lo+softness, d)
                              * (1.0-smoothstep(hi-softness, hi+softness, d)));
    }
    return 1.0-coverage;
}

// 接收平面的深度导数随每个采样点校正，避免大常量偏移导致阴影脱离物体。
float shadow_caster_contrib(sampler2DShadow shadowmap, vec4 shadowpos) {
    vec3 p = shadowpos.xyz / shadowpos.w;
    vec3 dx = dFdx(p), dy = dFdy(p);
    float det = dx.x * dy.y - dx.y * dy.x;
    vec2 slope = vec2(0.0);
    if (abs(det) > 1e-12) {
        slope = vec2(dy.y * dx.z - dx.y * dy.z,
                     dx.x * dy.z - dy.x * dx.z) / det;
    }
    vec2 texel = 1.0 / vec2(textureSize(shadowmap, 0));
    float bias = global_shadow_bias + min(dot(abs(slope), texel) * 0.5, 0.0003);
    // 车辆/设施的有限实时投影在覆盖边缘渐退；连续护栏由独立遮蔽保持。
    vec3 edge = min(p, vec3(1.0) - p);
    float coverage = smoothstep(0.0, 0.12, min(edge.x, edge.y))
                   * smoothstep(0.0, 0.02, edge.z);
    if (coverage <= 0.0) {
        return 1.0;
    }
    float shadow = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            vec2 offset = vec2(x, y) * texel;
            vec2 uv = p.xy + offset;
            if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) {
                shadow += 1.0;
            } else {
                shadow += texture(shadowmap, vec3(uv, p.z + dot(slope, offset) - bias));
            }
        }
    }
    return mix(1.0, shadow / 9.0, coverage);
}
