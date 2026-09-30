#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 shore_uv;
out vec3 v_world_position;
void main() {
    shore_uv = p3d_MultiTexCoord0;
    v_world_position = (p3d_ModelMatrix * p3d_Vertex).xyz;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
