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
varying vec3 v_world_position;
varying vec4 v_color;
varying float v_occlude;
varying vec2 v_texcoord;
varying mat3 v_view_tbn;
varying mat3 v_world_tbn;

uniform int num_segments;
uniform vec2 radius;
uniform vec2 start_center;
uniform vec2 end_center;
uniform float y;
//uniform vec2 bending;

const float TAU = 6.283185307179586;

void main() {
    vec4 model_position = p3d_Vertex;
    vec3 model_normal = p3d_Normal;
    vec3 model_tangent = p3d_Tangent.xyz;

    float phi = p3d_Vertex.x * (TAU / (num_segments * 2));

    //phi += (y + p3d_Vertex.y + p3d_ModelMatrix[3].y) * 0.02;

    float rt = (p3d_Vertex.y / 40 + 0.5);
    float rad = (radius[1] * rt + radius[0] * (1-rt)) - p3d_Vertex.z;

    model_position.x = sin(phi) * rad;
    model_position.y = p3d_Vertex.y + p3d_ModelMatrix[3].y;
    model_position.z = -cos(phi) * rad;
    model_position.w = 1;

    vec2 center = (end_center * rt + start_center * (1-rt));
    model_position.xz += center;

    //vec2 bending = vec2(sin(y / 200), cos(y / 100)) * 0.01;
    vec2 bending = vec2(sin(y / 200), model_position.y) * 0.00002;

    model_normal += vec3(0, (radius[0] - radius[1]) / 40 + dot(normalize(model_position.xz), bending.xy * 4), 0);
    model_normal = normalize(model_normal);

    mat3 basis = mat3(
      vec3(cos(phi), 0, sin(phi)),
      vec3(0, 1, 0),
      vec3(-sin(phi), 0, cos(phi)));

    model_normal = basis * model_normal;
    model_tangent = basis * model_tangent;

    //model_normal = model_normal.zyx;

    vec4 world_position = model_position;

    world_position.x += world_position.y * world_position.y * bending.x * bending.x;
    world_position.z += world_position.y * world_position.y * bending.y * bending.y;

    vec4 view_position = p3d_ViewMatrix * world_position;
    v_world_position = model_position.xyz;
    v_view_position = view_position.xyz;
    v_color = p3d_Color;
    v_texcoord = (p3d_TextureMatrix * vec4(p3d_MultiTexCoord0, 0, 1)).xy;

    v_occlude = min(1.0, (p3d_Vertex.z + 4) / 5.0);

    vec3 view_normal = normalize(mat3(p3d_ViewMatrix) * model_normal);
    vec3 view_tangent = normalize(mat3(p3d_ViewMatrix) * model_tangent);
    vec3 view_bitangent = cross(view_normal, view_tangent) * p3d_Tangent.w;
    v_view_tbn = mat3(
        view_tangent,
        view_bitangent,
        view_normal
    );

    vec3 world_normal = model_normal;
    vec3 world_tangent = model_tangent;
    vec3 world_bitangent = cross(world_normal, world_tangent) * p3d_Tangent.w;
    v_world_tbn = mat3(
            world_tangent,
            world_bitangent,
            world_normal
    );

    gl_Position = p3d_ProjectionMatrix * view_position;
}
