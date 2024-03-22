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


varying vec3 v_world_position;
varying vec4 v_color;
varying vec2 v_texcoord;
varying mat3 v_world_tbn;

uniform int num_segments;
uniform vec2 radius;
uniform vec2 start_center;
uniform vec2 end_center;
uniform float y;
//uniform vec2 bending;

const float TAU = 6.283185307179586;
const vec4 fog_color = vec4(0.001, 0, 0, 1);

void main() {
    vec4 model_position = p3d_Vertex;
    vec3 model_normal = p3d_Normal;
    vec3 model_tangent = p3d_Tangent.xyz;

    float phi = p3d_Vertex.x * (TAU / (num_segments * 2));

    float rt = (p3d_Vertex.y / 40 + 0.5);
    float interp_radius = (radius[1] * rt + radius[0] * (1-rt));

    float world_y = p3d_Vertex.y + p3d_ModelMatrix[3].y;
    float effect_fac = smoothstep(20, 100, world_y) * 5 / interp_radius;
    phi += effect_fac * sin(y / 25);

    //phi += (y + p3d_Vertex.y + p3d_ModelMatrix[3].y) * 0.02;

    float rad = interp_radius - p3d_Vertex.z;

    model_position.x = sin(phi) * rad;
    model_position.y = p3d_Vertex.y + p3d_ModelMatrix[3].y;
    model_position.z = -cos(phi) * rad;
    model_position.w = 1;

    vec2 center = (end_center * rt + start_center * (1-rt));
    model_position.xz += center;

    //vec2 bending = vec2(sin(y / 20), cos(y / 10)) * 0.0001 * effect_fac;
    //vec2 bending = vec2(sin(y / 200), model_position.y) * 0.00002;
    float clamped_world_y = max(0, world_y - 10);
    vec2 bending = vec2(sin(y / 177), cos(y / 13)) * 0.001 * clamped_world_y * clamped_world_y;

    model_normal += vec3(0, (radius[0] - radius[1]) / 40 + dot(normalize(model_position.xz), bending.xy) * 0.1, 0);
    model_normal = normalize(model_normal);

    mat3 basis = mat3(
      vec3(cos(phi), 0, sin(phi)),
      vec3(0, 1, 0),
      vec3(-sin(phi), 0, cos(phi)));

    model_normal = basis * model_normal;
    model_tangent = basis * model_tangent;

    //model_normal = model_normal.zyx;

    vec4 world_position = model_position;

    world_position.x += bending.x;
    world_position.z += bending.y;

    vec4 view_position = p3d_ViewMatrix * world_position;
    v_world_position = world_position.xyz;
    v_color = p3d_Color;
    v_texcoord = (p3d_TextureMatrix * vec4(p3d_MultiTexCoord0, 0, 1)).xy;

    // occlude
    v_color.a = min(1.0, (p3d_Vertex.z + 4) / 5.0);

    // Exponential fog
    float fog_distance = length(view_position.xyz / view_position.w);
    float fog_factor = clamp(1.0 / exp(fog_distance * 0.04), 0.0, 1.0);
    v_color.a *= fog_factor;

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
