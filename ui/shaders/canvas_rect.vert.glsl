#version 410

// Per-vertex
layout(location = 0) in vec2 a_unitPos;          // [0,1] x [0,1]

// Per-instance
layout(location = 1) in vec4 i_rect;             // x, y, w, h (pixel space)
layout(location = 2) in vec4 i_borderRadius;     // tl, tr, br, bl
layout(location = 3) in vec4 i_borderSize;       // top, right, bottom, left
layout(location = 4) in uint i_bgColor;          // ARGB packed
layout(location = 5) in uint i_borderColorTop;
layout(location = 6) in uint i_borderColorRight;
layout(location = 7) in uint i_borderColorBottom;
layout(location = 8) in uint i_borderColorLeft;
layout(location = 9) in uint i_clipIndex;

// The projection, then the logical canvas size followed by the actual, rounded framebuffer size.
// One std140 block, the same in every canvas shader: Vulkan's GLSL has no plain uniforms.
layout(std140) uniform Canvas {
    mat4 u_projection;
    vec4 u_canvasMetrics;
};

layout(location = 0) flat out vec2 v_rectOrigin;
layout(location = 1) flat out vec4 v_rectSize;  // (w, h, w, h) for convenience
layout(location = 2) flat out vec4 v_borderRadius;
layout(location = 3) flat out vec4 v_borderSize;
layout(location = 4) flat out uint v_bgColor;
layout(location = 5) flat out uint v_borderColorTop;
layout(location = 6) flat out uint v_borderColorRight;
layout(location = 7) flat out uint v_borderColorBottom;
layout(location = 8) flat out uint v_borderColorLeft;
layout(location = 9) flat out uint v_clipIndex;
// Whether the rect grew to fade an edge between device pixels; a rect on the grid is drawn exactly as before.
layout(location = 10) flat out float v_fadesEdges;

void main() {
    // A rect moved or scaled by a transform can have an edge between device pixels. The quad grows a
    // pixel on that axis so the pixels the edge partly covers are drawn, and the fragment shader fades
    // them by how much. An edge on the grid needs neither and the quad stays as it was.
    vec2 devicePerLogical = u_canvasMetrics.zw / u_canvasMetrics.xy;
    vec2 low = i_rect.xy * devicePerLogical;
    vec2 high = (i_rect.xy + i_rect.zw) * devicePerLogical;
    vec2 offGrid = max(abs(low - round(low)), abs(high - round(high)));
    // A rect with no area stays without one rather than growing into a faint line.
    bool hasArea = i_rect.z > 0.0 && i_rect.w > 0.0;
    vec2 outset = hasArea ? step(1.0 / 256.0, offGrid) / devicePerLogical : vec2(0.0);
    v_fadesEdges = outset.x > 0.0 || outset.y > 0.0 ? 1.0 : 0.0;
    vec2 pixelPos = i_rect.xy - outset + a_unitPos * (i_rect.zw + 2.0 * outset);
    gl_Position = u_projection * vec4(pixelPos, 0.0, 1.0);

    v_rectOrigin = i_rect.xy;
    v_rectSize = vec4(i_rect.zw, i_rect.zw);
    v_borderRadius = i_borderRadius;
    v_borderSize = i_borderSize;
    v_bgColor = i_bgColor;
    v_borderColorTop = i_borderColorTop;
    v_borderColorRight = i_borderColorRight;
    v_borderColorBottom = i_borderColorBottom;
    v_borderColorLeft = i_borderColorLeft;
    v_clipIndex = i_clipIndex;
}
