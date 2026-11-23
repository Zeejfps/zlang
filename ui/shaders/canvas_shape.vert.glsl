#version 410

// Per-vertex
layout(location = 0) in vec2 a_unitPos;          // [0,1] x [0,1]

// Per-instance
layout(location = 1) in vec4 i_outerRect;        // x, y, w, h pixel space (drawn quad)
layout(location = 2) in vec4 i_shapeData;        // line: p0.xy/p1.xy; circle: center.xy/radius; bezier: p0.xy/control.xy
layout(location = 3) in vec4 i_shapeData2;       // bezier: p2.xy in .xy; line: dash/gap in .zw
layout(location = 4) in float i_halfWidth;
layout(location = 5) in uint i_color;            // ARGB packed
layout(location = 6) in uint i_shapeType;        // 0 filled circle, 1 ring, 2 line/capsule, 3 quad bezier
layout(location = 7) in uint i_clipIndex;
layout(location = 8) in uint i_color2;           // line gradient end
layout(location = 9) in uint i_flags;            // bits 0-1 cap, bit 2 dash, bit 3 gradient

// The projection, then the logical canvas size followed by the actual, rounded framebuffer size.
// One std140 block, the same in every canvas shader: Vulkan's GLSL has no plain uniforms.
layout(std140) uniform Canvas {
    mat4 u_projection;
    vec4 u_canvasMetrics;
};

layout(location = 0) out vec2 v_pixelPos;
layout(location = 1) out vec4 v_shapeData;
layout(location = 2) out vec4 v_shapeData2;
layout(location = 3) flat out float v_halfWidth;
layout(location = 4) flat out uint v_color;
layout(location = 5) flat out uint v_shapeType;
layout(location = 6) flat out uint v_clipIndex;
layout(location = 7) flat out uint v_color2;
layout(location = 8) flat out uint v_flags;

void main() {
    vec2 pixelPos = i_outerRect.xy + a_unitPos * i_outerRect.zw;
    gl_Position = u_projection * vec4(pixelPos, 0.0, 1.0);

    v_pixelPos = pixelPos;
    v_shapeData = i_shapeData;
    v_shapeData2 = i_shapeData2;
    v_halfWidth = i_halfWidth;
    v_color = i_color;
    v_shapeType = i_shapeType;
    v_clipIndex = i_clipIndex;
    v_color2 = i_color2;
    v_flags = i_flags;
}
