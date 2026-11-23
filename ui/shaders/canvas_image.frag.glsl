#version 410

layout(location = 0) in vec2 v_pixelPos;
layout(location = 1) in vec2 v_uv;
layout(location = 2) in vec2 v_local;
layout(location = 3) flat in vec2 v_halfSize;
layout(location = 4) flat in vec4 v_srcUV;
layout(location = 5) flat in float v_fadesEdges;
layout(location = 6) flat in uint v_tint;
layout(location = 7) flat in uint v_clipIndex;
layout(location = 8) flat in vec4 v_cornerRadius;

layout(std140) uniform ClipRects {
    vec4 u_clipRects[256];  // (left, bottom, right, top)
    vec4 u_clipRounds[256]; // the rounded rect the clip is also cut to, (left, bottom, right, top)
    vec4 u_clipRadii[256];  // that rect's corner radius in x; 0 when the clip is not rounded
};

uniform sampler2D u_texture;
// The projection, then the logical canvas size followed by the actual, rounded framebuffer size.
// One std140 block, the same in every canvas shader: Vulkan's GLSL has no plain uniforms.
layout(std140) uniform Canvas {
    mat4 u_projection;
    vec4 u_canvasMetrics;
};

out vec4 f_Color;

vec4 unpackARGB(uint c) {
    float a = float((c >> 24) & 0xFFu) / 255.0;
    float r = float((c >> 16) & 0xFFu) / 255.0;
    float g = float((c >>  8) & 0xFFu) / 255.0;
    float b = float( c        & 0xFFu) / 255.0;
    return vec4(r, g, b, a);
}

// How much of the pixel at p the clip's rounded rect covers: 1 inside it, 0 outside, and between over
// the device pixel its edge crosses. Always 1 for a clip that is not rounded.
float clipCoverage(vec2 p, uint index) {
    float pixel = max(fwidth(p.x), 1e-4);
    float r = u_clipRadii[index].x;
    if (r <= 0.0) return 1.0;
    vec4 rounded = u_clipRounds[index];
    vec2 halfSize = (rounded.zw - rounded.xy) * 0.5;
    vec2 q = abs(p - (rounded.xy + rounded.zw) * 0.5) - (halfSize - vec2(r));
    float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
    return clamp(0.5 - d / pixel, 0.0, 1.0);
}

void main() {
    float clipCover = clipCoverage(v_pixelPos, v_clipIndex);
    vec4 clip = u_clipRects[v_clipIndex];
    if (v_pixelPos.x < clip.x || v_pixelPos.x >= clip.z ||
        v_pixelPos.y < clip.y || v_pixelPos.y >= clip.w) {
        discard;
    }
    if (clipCover <= 0.0) discard;

    // An edge between device pixels fades the pixels it partly covers, by how much it covers them.
    float coverage = 1.0;
    if (v_fadesEdges > 0.0) {
        vec2 devicePerLogical = u_canvasMetrics.zw / u_canvasMetrics.xy;
        vec2 inside = (v_halfSize - abs(v_local)) * devicePerLogical;
        coverage = clamp(inside.x + 0.5, 0.0, 1.0) * clamp(inside.y + 0.5, 0.0, 1.0);
        if (coverage <= 0.0) discard;
    }

    // Rounded corners cut the image to their shape, smoothing its edge there over a device pixel. The
    // canvas's y runs up, so a positive local y is the image's upper half.
    float radius = v_local.y > 0.0
        ? (v_local.x > 0.0 ? v_cornerRadius.y : v_cornerRadius.x)
        : (v_local.x > 0.0 ? v_cornerRadius.z : v_cornerRadius.w);
    if (radius > 0.0) {
        vec2 devicePerLogical = u_canvasMetrics.zw / u_canvasMetrics.xy;
        vec2 q = abs(v_local) - (v_halfSize - vec2(radius));
        float distance = length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - radius;
        coverage *= clamp(0.5 - distance * devicePerLogical.x, 0.0, 1.0);
        if (coverage <= 0.0) discard;
    }

    vec2 uvEnd = v_srcUV.xy + v_srcUV.zw;
    vec2 uv = clamp(v_uv, min(v_srcUV.xy, uvEnd), max(v_srcUV.xy, uvEnd));
    vec4 sample0 = texture(u_texture, uv);
    vec4 tint = unpackARGB(v_tint);
    f_Color = sample0 * tint * vec4(1.0, 1.0, 1.0, coverage);
    f_Color.a *= clipCover;
}
