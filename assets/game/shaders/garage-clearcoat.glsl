// 车库车漆的无色透明面层；IOR 1.5，粗糙度0.10。
// 分层依据KHR_materials_clearcoat，沿用当前PBR的GGX、阴影和BRDF积分。
const float garage_coat_roughness = 0.10;

vec3 garage_coat_direct(FunctionParamters base, vec3 light_color, float shadow) {
    base.roughness = garage_coat_roughness * garage_coat_roughness;
    return base.n_dot_l * light_color * visibility_occlusion(base)
        * microfacet_distribution(base) * shadow;
}

vec3 garage_coat_layer(vec3 base, float n_dot_v, vec3 reflection,
                      vec3 direct, float occlusion) {
    float fresnel = 0.04 + 0.96 * pow(1.0 - n_dot_v, 5.0);
    vec2 integrated = texture2D(brdf_lut, vec2(n_dot_v, garage_coat_roughness)).rg;
    vec3 environment = textureCubeLod(filtered_env_map, reflection,
        garage_coat_roughness * max_reflection_lod).rgb;
    vec3 indirect = environment * (fresnel * integrated.x + integrated.y) * occlusion;
    return base * (1.0 - fresnel) + direct * fresnel + indirect;
}
