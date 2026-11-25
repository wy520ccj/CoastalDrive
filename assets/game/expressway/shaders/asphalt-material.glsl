// 从道路真实UV的屏幕导数构建切线，不改原物理网格或依赖缺失的顶点tangent。
uniform sampler2D asphalt_normals;
uniform sampler2D asphalt_roughness;
vec4 asphalt_color() {
    vec3 photograph = texture2D(p3d_TextureBaseColor,v_texcoord).rgb;
    float gray = dot(photograph,vec3(0.2126,0.7152,0.0722));
    return vec4(mix(photograph,vec3(gray),0.85),1.0);
}
vec3 asphalt_normal(vec3 geometric_normal, vec3 position) {
    vec3 n = normalize(geometric_normal);
    vec3 dx = dFdx(position), dy = dFdy(position);
    vec2 ux = dFdx(v_texcoord), uy = dFdy(v_texcoord);
    vec3 py = cross(dy, n), px = cross(n, dx);
    vec3 tangent = py * ux.x + px * uy.x;
    vec3 bitangent = py * ux.y + px * uy.y;
    float magnitude = max(dot(tangent,tangent), dot(bitangent,bitangent));
    if (magnitude < 1e-16) return n;
    mat3 basis = mat3(tangent,bitangent,n);
    vec3 detail = texture2D(asphalt_normals,v_texcoord).rgb*2.0-1.0;
    float dist = length(position);
    detail.xy *= mix(0.32, 0.06, smoothstep(10.0, 45.0, dist));
    detail.z *= sqrt(magnitude);
    return normalize(basis * detail);
}
