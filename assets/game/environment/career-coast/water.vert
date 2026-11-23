#version 330
#define CAREER_COAST
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 shore_uv;
out vec3 v_world_position;
#ifdef CAREER_COAST
uniform float career_origin_y;
#endif
void main() {
    shore_uv = p3d_MultiTexCoord0;
    v_world_position = (p3d_ModelMatrix * p3d_Vertex).xyz;
#ifdef CAREER_COAST
    float world_y = v_world_position.y+career_origin_y;
    // 有限海面顶点不能先取模，否则跨600米的三角形会插值倒退。
    shore_uv = vec2(v_world_position.x-30.-.12*world_y-20.*sin(world_y/240.),world_y);
#endif
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
