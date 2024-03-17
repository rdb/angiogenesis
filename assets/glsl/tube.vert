#version 120

uniform mat4 p3d_ProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat3 p3d_NormalMatrix;
uniform mat4 p3d_TextureMatrix;
uniform mat4 p3d_ModelMatrixInverseTranspose;

attribute vec4 p3d_Vertex;
attribute vec4 p3d_Color;
attribute vec3 p3d_Normal;
attribute vec4 p3d_Tangent;
attribute vec2 p3d_MultiTexCoord0;


varying vec3 v_view_position;
varying vec4 v_color;
varying vec2 v_texcoord;
varying mat3 v_view_tbn;

uniform int num_segments;
uniform vec2 radius;
uniform float y;
//uniform vec2 bending;
const float TAU = 6.283185307179586;

void main() {
    vec4 model_position = p3d_Vertex;
    vec3 model_normal = p3d_Normal;
    vec3 model_tangent = p3d_Tangent.xyz;

    float phi = p3d_Vertex.x * (TAU / (num_segments * 2));

    //phi += (y + p3d_Vertex.y + p3d_ModelMatrix[3].y) * 0.02;

    float rt = (p3d_Vertex.y / 10 + 0.5);
    float rad = (radius[1] * rt + radius[0] * (1-rt)) - p3d_Vertex.z;
    model_position.x = cos(phi) * rad;
    model_position.y = p3d_Vertex.y;
    model_position.z = sin(phi) * rad;
    model_position.w = 1;

    vec4 world_position = p3d_ModelMatrix * model_position;
    world_position.xyzw /= world_position.w;

    //vec2 bending = vec2(sin(y / 200), cos(y / 100)) * 0.01;
    vec2 bending = vec2(sin(y / 200), world_position.y) * 0.00005;

    world_position.x += world_position.y * world_position.y * bending.x * bending.x;
    world_position.z += world_position.y * world_position.y * bending.y * bending.y;

    vec4 view_position = p3d_ViewMatrix * world_position;
    v_view_position = (view_position).xyz;
    v_color = p3d_Color;
    v_texcoord = (p3d_TextureMatrix * vec4(p3d_MultiTexCoord0, 0, 1)).xy;

    v_color.rgb *= (p3d_Vertex.z + 2.0) / 3.0;

    vec3 view_normal = normalize(p3d_NormalMatrix * model_normal);
    vec3 view_tangent = normalize(p3d_NormalMatrix * model_tangent);
    vec3 view_bitangent = cross(view_normal, view_tangent) * p3d_Tangent.w;
    v_view_tbn = mat3(
        view_tangent,
        view_bitangent,
        view_normal
    );

    gl_Position = p3d_ProjectionMatrix * view_position;
}
