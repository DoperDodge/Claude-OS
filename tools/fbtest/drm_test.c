/*
 * Claude-OS DRM Framebuffer Test
 *
 * Minimal program that opens /dev/dri/card0 (virtio-gpu in QEMU),
 * creates a dumb framebuffer, and draws colored rectangles to prove
 * that the graphics pipeline works end-to-end.
 *
 * Build (on target):
 *   gcc -o drm_test drm_test.c -ldrm -I/usr/include/libdrm
 *
 * Cross-compile (from host):
 *   aarch64-linux-gnu-gcc -o drm_test drm_test.c -ldrm -I/usr/include/libdrm
 *
 * Run:
 *   ./drm_test          # Draws test pattern for 5 seconds
 *   ./drm_test --hold   # Draws test pattern until Enter is pressed
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

struct framebuffer {
    int fd;
    uint32_t fb_id;
    uint32_t handle;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t size;
    uint32_t *map;
};

static int create_fb(int fd, uint32_t width, uint32_t height, struct framebuffer *fb) {
    struct drm_mode_create_dumb create = {0};
    struct drm_mode_map_dumb map_req = {0};

    fb->fd = fd;
    fb->width = width;
    fb->height = height;

    /* Create a dumb buffer */
    create.width = width;
    create.height = height;
    create.bpp = 32;
    if (ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &create) < 0) {
        perror("DRM_IOCTL_MODE_CREATE_DUMB");
        return -1;
    }

    fb->handle = create.handle;
    fb->stride = create.pitch;
    fb->size = create.size;

    /* Create framebuffer object */
    if (drmModeAddFB(fd, width, height, 24, 32, fb->stride, fb->handle, &fb->fb_id) != 0) {
        perror("drmModeAddFB");
        return -1;
    }

    /* Map buffer to userspace */
    map_req.handle = fb->handle;
    if (ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map_req) < 0) {
        perror("DRM_IOCTL_MODE_MAP_DUMB");
        return -1;
    }

    fb->map = mmap(0, fb->size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map_req.offset);
    if (fb->map == MAP_FAILED) {
        perror("mmap");
        return -1;
    }

    return 0;
}

static void destroy_fb(struct framebuffer *fb) {
    struct drm_mode_destroy_dumb destroy = {0};

    if (fb->map)
        munmap(fb->map, fb->size);

    drmModeRmFB(fb->fd, fb->fb_id);

    destroy.handle = fb->handle;
    ioctl(fb->fd, DRM_IOCTL_MODE_DESTROY_DUMB, &destroy);
}

static void fill_rect(struct framebuffer *fb, uint32_t x, uint32_t y,
                       uint32_t w, uint32_t h, uint32_t color) {
    for (uint32_t row = y; row < y + h && row < fb->height; row++) {
        for (uint32_t col = x; col < x + w && col < fb->width; col++) {
            fb->map[row * (fb->stride / 4) + col] = color;
        }
    }
}

static void draw_test_pattern(struct framebuffer *fb) {
    uint32_t w = fb->width;
    uint32_t h = fb->height;

    /* Background: Claude-OS Navy (#1A1A2E) */
    fill_rect(fb, 0, 0, w, h, 0xFF1A1A2E);

    /* Status bar area: semi-transparent dark */
    fill_rect(fb, 0, 0, w, 54, 0xFF0D0D1A);

    /* Claude Terracotta accent bar */
    fill_rect(fb, 0, 54, w, 4, 0xFFD4A574);

    /* Center card: Sand color (#E8D5C4) */
    uint32_t card_w = w * 3 / 4;
    uint32_t card_h = h / 3;
    uint32_t card_x = (w - card_w) / 2;
    uint32_t card_y = (h - card_h) / 2;
    fill_rect(fb, card_x, card_y, card_w, card_h, 0xFFE8D5C4);

    /* Inner accent rectangle: Terracotta */
    uint32_t inner_w = card_w - 40;
    uint32_t inner_h = 60;
    uint32_t inner_x = card_x + 20;
    uint32_t inner_y = card_y + 20;
    fill_rect(fb, inner_x, inner_y, inner_w, inner_h, 0xFFD4A574);

    /* Color test strips at bottom */
    uint32_t strip_h = 40;
    uint32_t strip_y = h - strip_h - 80;
    uint32_t strip_w = w / 6;
    fill_rect(fb, strip_w * 0, strip_y, strip_w, strip_h, 0xFFFF0000); /* Red */
    fill_rect(fb, strip_w * 1, strip_y, strip_w, strip_h, 0xFF00FF00); /* Green */
    fill_rect(fb, strip_w * 2, strip_y, strip_w, strip_h, 0xFF0000FF); /* Blue */
    fill_rect(fb, strip_w * 3, strip_y, strip_w, strip_h, 0xFFFFFF00); /* Yellow */
    fill_rect(fb, strip_w * 4, strip_y, strip_w, strip_h, 0xFFFF00FF); /* Magenta */
    fill_rect(fb, strip_w * 5, strip_y, strip_w, strip_h, 0xFF00FFFF); /* Cyan */

    /* Home indicator pill at bottom */
    uint32_t pill_w = 134;
    uint32_t pill_h = 5;
    uint32_t pill_x = (w - pill_w) / 2;
    uint32_t pill_y = h - 20;
    fill_rect(fb, pill_x, pill_y, pill_w, pill_h, 0x80FFFFFF);
}

int main(int argc, char *argv[]) {
    int fd;
    int hold = 0;
    drmModeRes *resources;
    drmModeConnector *connector = NULL;
    drmModeEncoder *encoder = NULL;
    drmModeCrtc *crtc = NULL;
    struct framebuffer fb = {0};

    if (argc > 1 && strcmp(argv[1], "--hold") == 0)
        hold = 1;

    /* Open DRM device */
    fd = open("/dev/dri/card0", O_RDWR);
    if (fd < 0) {
        perror("open /dev/dri/card0");
        fprintf(stderr, "Hint: Make sure QEMU was launched with --gui (virtio-gpu)\n");
        return 1;
    }

    /* Get DRM resources */
    resources = drmModeGetResources(fd);
    if (!resources) {
        perror("drmModeGetResources");
        close(fd);
        return 1;
    }

    /* Find first connected connector */
    for (int i = 0; i < resources->count_connectors; i++) {
        connector = drmModeGetConnector(fd, resources->connectors[i]);
        if (connector && connector->connection == DRM_MODE_CONNECTED && connector->count_modes > 0)
            break;
        drmModeFreeConnector(connector);
        connector = NULL;
    }

    if (!connector) {
        fprintf(stderr, "No connected display found\n");
        drmModeFreeResources(resources);
        close(fd);
        return 1;
    }

    /* Use the preferred mode (first mode) */
    drmModeModeInfo *mode = &connector->modes[0];
    printf("[Claude-OS fbtest] Display: %ux%u @ %uHz\n", mode->hdisplay, mode->vdisplay, mode->vrefresh);

    /* Find encoder and CRTC */
    encoder = drmModeGetEncoder(fd, connector->encoder_id);
    if (!encoder) {
        /* Try the first supported encoder */
        for (int i = 0; i < resources->count_encoders; i++) {
            encoder = drmModeGetEncoder(fd, resources->encoders[i]);
            if (encoder)
                break;
        }
    }

    if (!encoder) {
        fprintf(stderr, "No encoder found\n");
        drmModeFreeConnector(connector);
        drmModeFreeResources(resources);
        close(fd);
        return 1;
    }

    /* Save current CRTC for restoration */
    crtc = drmModeGetCrtc(fd, encoder->crtc_id);

    /* Create framebuffer */
    if (create_fb(fd, mode->hdisplay, mode->vdisplay, &fb) < 0) {
        fprintf(stderr, "Failed to create framebuffer\n");
        drmModeFreeEncoder(encoder);
        drmModeFreeConnector(connector);
        drmModeFreeResources(resources);
        close(fd);
        return 1;
    }

    /* Draw the Claude-OS test pattern */
    draw_test_pattern(&fb);

    /* Set the framebuffer on the CRTC */
    if (drmModeSetCrtc(fd, encoder->crtc_id, fb.fb_id, 0, 0,
                       &connector->connector_id, 1, mode) != 0) {
        perror("drmModeSetCrtc");
        destroy_fb(&fb);
        drmModeFreeEncoder(encoder);
        drmModeFreeConnector(connector);
        drmModeFreeResources(resources);
        close(fd);
        return 1;
    }

    printf("[Claude-OS fbtest] Test pattern displayed successfully!\n");
    printf("[Claude-OS fbtest] Claude-OS Navy background + Terracotta accents + color strips\n");

    if (hold) {
        printf("[Claude-OS fbtest] Press Enter to exit...\n");
        getchar();
    } else {
        printf("[Claude-OS fbtest] Displaying for 5 seconds...\n");
        sleep(5);
    }

    /* Restore previous CRTC state */
    if (crtc) {
        drmModeSetCrtc(fd, crtc->crtc_id, crtc->buffer_id, crtc->x, crtc->y,
                       &connector->connector_id, 1, &crtc->mode);
        drmModeFreeCrtc(crtc);
    }

    destroy_fb(&fb);
    drmModeFreeEncoder(encoder);
    drmModeFreeConnector(connector);
    drmModeFreeResources(resources);
    close(fd);

    printf("[Claude-OS fbtest] Done.\n");
    return 0;
}
