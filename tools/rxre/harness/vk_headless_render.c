// vk_headless_render — headless offscreen Vulkan graphics harness (POLARIS-040).
// Renders vertex.spv + fragment.spv into a 64x64 RGBA image and dumps raw pixels.
// Usage: vk_headless_render <vert.spv> <frag.spv> <dump.rgba> [--tex] [--draw N] [--attrs N]
// RADV_DEBUG=asm dumps GFX8 ISA at pipeline-compile time to stderr/stdout.
// IMPORTANT: unprepared fragment shaders may hang/crash the GPU (observed on the
// Polaris12 RX 550 with the goverlay demo pipelines). Use only deliberately.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <vulkan/vulkan.h>

static const char *skip_str(int argc, char **argv, const char *name) {
    for (int i = 0; i < argc - 1; i++) if (!strcmp(argv[i], name)) return argv[i + 1];
    return NULL;
}
static int has_flag(int argc, char **argv, const char *name) {
    for (int i = 0; i < argc; i++) if (!strcmp(argv[i], name)) return 1;
    return 0;
}
static char *read_file(const char *path, size_t *sz) {
    FILE *f = fopen(path, "rb"); if (!f) return NULL;
    fseek(f, 0, SEEK_END); long s = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = malloc(s); fread(buf, 1, s, f); fclose(f); *sz = s; return buf;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "Usage: %s vert.spv frag.spv dump.rgba [--tex] [--draw N] [--attrs N]\n", argv[0]); return 1; }
    const char *vpath = argv[1], *fpath = argv[2], *dump = argv[3];
    int use_tex = has_flag(argc, argv, "--tex");
    int no_run = has_flag(argc, argv, "--no-run");
    int draw_verts = skip_str(argc, argv, "--draw") ? atoi(skip_str(argc, argv, "--draw")) : 64;
    int nattrs = skip_str(argc, argv, "--attrs") ? atoi(skip_str(argc, argv, "--attrs")) : 4;

    VkInstance instance;
    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName = "vk_headless_render"; app.apiVersion = VK_API_VERSION_1_0;
    VkInstanceCreateInfo ici = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    ici.pApplicationInfo = &app;
    if (vkCreateInstance(&ici, NULL, &instance) != VK_SUCCESS) { fprintf(stderr, "NO_INSTANCE\n"); return 2; }

    uint32_t dc = 0; vkEnumeratePhysicalDevices(instance, &dc, NULL);
    VkPhysicalDevice *devs = malloc(dc * sizeof(VkPhysicalDevice));
    vkEnumeratePhysicalDevices(instance, &dc, devs);
    VkPhysicalDevice pdev = VK_NULL_HANDLE;
    for (uint32_t i = 0; i < dc; i++) {
        VkPhysicalDeviceProperties pr; vkGetPhysicalDeviceProperties(devs[i], &pr);
        if (pr.vendorID == 0x1002u) { pdev = devs[i]; fprintf(stderr, "DEVICE: %s\n", pr.deviceName); }
    }
    free(devs);
    if (pdev == VK_NULL_HANDLE) { fprintf(stderr, "NO_AMD_GPU\n"); return 3; }

    uint32_t qfCount = 0; vkGetPhysicalDeviceQueueFamilyProperties(pdev, &qfCount, NULL);
    VkQueueFamilyProperties *qf = malloc(qfCount * sizeof(VkQueueFamilyProperties));
    vkGetPhysicalDeviceQueueFamilyProperties(pdev, &qfCount, qf);
    uint32_t qfIndex = UINT32_MAX;
    for (uint32_t i = 0; i < qfCount; i++) if (qf[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) { qfIndex = i; break; }
    free(qf);
    if (qfIndex == UINT32_MAX) { fprintf(stderr, "NO_GRAPHICS_QUEUE\n"); return 4; }

    VkPhysicalDeviceMemoryProperties memProps; vkGetPhysicalDeviceMemoryProperties(pdev, &memProps);
    uint32_t hostMem = UINT32_MAX, deviceLocal = UINT32_MAX;
    for (uint32_t i = 0; i < memProps.memoryTypeCount; i++) {
        VkMemoryPropertyFlags fl = memProps.memoryTypes[i].propertyFlags;
        if (hostMem == UINT32_MAX && (fl & (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) == (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) hostMem = i;
        if (deviceLocal == UINT32_MAX && (fl & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) deviceLocal = i;
    }

    VkDevice device; float qp = 1.0f;
    VkDeviceQueueCreateInfo dqci = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    dqci.queueFamilyIndex = qfIndex; dqci.queueCount = 1; dqci.pQueuePriorities = &qp;
    VkDeviceCreateInfo dci = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    dci.queueCreateInfoCount = 1; dci.pQueueCreateInfos = &dqci;
    if (vkCreateDevice(pdev, &dci, NULL, &device) != VK_SUCCESS) { fprintf(stderr, "NO_DEVICE\n"); return 5; }
    VkQueue queue; vkGetDeviceQueue(device, qfIndex, 0, &queue);

    VkImage img; VkImageCreateInfo imci = {VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    imci.imageType = VK_IMAGE_TYPE_2D; imci.format = VK_FORMAT_R8G8B8A8_UNORM;
    imci.extent.width = 64; imci.extent.height = 64; imci.extent.depth = 1;
    imci.mipLevels = 1; imci.arrayLayers = 1; imci.samples = VK_SAMPLE_COUNT_1_BIT;
    imci.tiling = VK_IMAGE_TILING_OPTIMAL;
    imci.usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
    imci.sharingMode = VK_SHARING_MODE_EXCLUSIVE; imci.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    if (vkCreateImage(device, &imci, NULL, &img) != VK_SUCCESS) { fprintf(stderr, "NO_IMAGE\n"); return 6; }
    VkMemoryRequirements req; vkGetImageMemoryRequirements(device, img, &req);
    VkDeviceMemory imgMem;
    VkMemoryAllocateInfo mai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
    mai.allocationSize = req.size; mai.memoryTypeIndex = deviceLocal;
    if (vkAllocateMemory(device, &mai, NULL, &imgMem) != VK_SUCCESS) { fprintf(stderr, "NO_IMG_MEM\n"); return 7; }
    vkBindImageMemory(device, img, imgMem, 0);
    VkImageView view; VkImageViewCreateInfo ivci = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
    ivci.image = img; ivci.viewType = VK_IMAGE_VIEW_TYPE_2D; ivci.format = VK_FORMAT_R8G8B8A8_UNORM;
    ivci.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT; ivci.subresourceRange.levelCount = 1; ivci.subresourceRange.layerCount = 1;
    vkCreateImageView(device, &ivci, NULL, &view);

    VkAttachmentDescription att = {0};
    att.format = VK_FORMAT_R8G8B8A8_UNORM; att.samples = VK_SAMPLE_COUNT_1_BIT;
    att.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR; att.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    att.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE; att.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    att.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED; att.finalLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    VkAttachmentReference ref = {0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
    VkSubpassDescription sub = {0};
    sub.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    sub.colorAttachmentCount = 1; sub.pColorAttachments = &ref;
    VkRenderPassCreateInfo rpci = {VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};
    rpci.attachmentCount = 1; rpci.pAttachments = &att; rpci.subpassCount = 1; rpci.pSubpasses = &sub;
    VkRenderPass renderPass; vkCreateRenderPass(device, &rpci, NULL, &renderPass);
    VkFramebuffer fb; VkFramebufferCreateInfo fbci = {VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};
    fbci.renderPass = renderPass; fbci.attachmentCount = 1; fbci.pAttachments = &view; fbci.width = 64; fbci.height = 64; fbci.layers = 1;
    vkCreateFramebuffer(device, &fbci, NULL, &fb);

    size_t vsize; char *vcode = read_file(vpath, &vsize);
    size_t fsize; char *fcode = read_file(fpath, &fsize);
    if (!vcode || !fcode) { fprintf(stderr, "NO_SHADER_FILE\n"); return 8; }
    VkShaderModule vmod = VK_NULL_HANDLE, fmod = VK_NULL_HANDLE;
    VkShaderModuleCreateInfo smci = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
    smci.codeSize = vsize; smci.pCode = (const uint32_t *)vcode;
    if (vkCreateShaderModule(device, &smci, NULL, &vmod) != VK_SUCCESS) { fprintf(stderr, "BAD_VERT_MODULE\n"); return 9; }
    smci.codeSize = fsize; smci.pCode = (const uint32_t *)fcode;
    if (vkCreateShaderModule(device, &smci, NULL, &fmod) != VK_SUCCESS) { fprintf(stderr, "BAD_FRAG_MODULE\n"); return 10; }

    VkDescriptorSetLayoutBinding texBinding = {0};
    texBinding.binding = 0; texBinding.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    texBinding.descriptorCount = 1; texBinding.stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;
    VkDescriptorSetLayoutCreateInfo dslci = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    dslci.bindingCount = 1; dslci.pBindings = &texBinding;
    VkDescriptorSetLayout setLayout; vkCreateDescriptorSetLayout(device, &dslci, NULL, &setLayout);
    VkPipelineLayoutCreateInfo plci = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    VkPushConstantRange pcr = {VK_SHADER_STAGE_FRAGMENT_BIT, 0, 128};
    plci.setLayoutCount = 1; plci.pSetLayouts = &setLayout;
    plci.pushConstantRangeCount = 1; plci.pPushConstantRanges = &pcr;
    VkPipelineLayout pipeLayout; vkCreatePipelineLayout(device, &plci, NULL, &pipeLayout);

    VkPipelineShaderStageCreateInfo stages[2] = {0};
    stages[0].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage = VK_SHADER_STAGE_VERTEX_BIT; stages[0].module = vmod; stages[0].pName = "main";
    stages[1].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[1].stage = VK_SHADER_STAGE_FRAGMENT_BIT; stages[1].module = fmod; stages[1].pName = "main";

    VkVertexInputBindingDescription bdesc = {0};
    bdesc.binding = 0; bdesc.stride = 16 * nattrs; bdesc.inputRate = VK_VERTEX_INPUT_RATE_VERTEX;
    VkVertexInputAttributeDescription adesc[16];
    for (int i = 0; i < nattrs && i < 16; i++) {
        adesc[i].location = i; adesc[i].binding = 0; adesc[i].format = VK_FORMAT_R32G32B32A32_SFLOAT; adesc[i].offset = i * 16;
    }
    VkPipelineVertexInputStateCreateInfo visci = {VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
    visci.vertexBindingDescriptionCount = 1; visci.pVertexBindingDescriptions = &bdesc;
    visci.vertexAttributeDescriptionCount = nattrs; visci.pVertexAttributeDescriptions = adesc;
    VkPipelineInputAssemblyStateCreateInfo iasci = {VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};
    iasci.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    VkPipelineViewportStateCreateInfo vpsci = {VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};
    VkViewport viewport = {0, 0, 64, 64, 0, 1}; VkRect2D sc = {{0, 0}, {64, 64}};
    vpsci.viewportCount = 1; vpsci.pViewports = &viewport; vpsci.scissorCount = 1; vpsci.pScissors = &sc;
    VkPipelineRasterizationStateCreateInfo rscci = {VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};
    rscci.polygonMode = VK_POLYGON_MODE_FILL; rscci.cullMode = VK_CULL_MODE_NONE; rscci.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE; rscci.lineWidth = 1.0f;
    VkPipelineMultisampleStateCreateInfo msci = {VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};
    msci.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
    VkPipelineColorBlendAttachmentState cba = {0};
    cba.blendEnable = VK_FALSE; cba.colorWriteMask = 0xF;
    VkPipelineColorBlendStateCreateInfo cbsci = {VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};
    cbsci.attachmentCount = 1; cbsci.pAttachments = &cba;
    VkPipelineDynamicStateCreateInfo dsci = {VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO};
    VkGraphicsPipelineCreateInfo gpci = {VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};
    gpci.stageCount = 2; gpci.pStages = stages; gpci.pVertexInputState = &visci; gpci.pInputAssemblyState = &iasci;
    gpci.pViewportState = &vpsci; gpci.pRasterizationState = &rscci; gpci.pMultisampleState = &msci; gpci.pColorBlendState = &cbsci; gpci.pDynamicState = &dsci;
    gpci.layout = pipeLayout; gpci.renderPass = renderPass; gpci.subpass = 0;
    VkPipeline pipeline;
    if (vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1, &gpci, NULL, &pipeline) != VK_SUCCESS) { fprintf(stderr, "NO_PIPELINE\n"); return 11; }
    if (no_run) { fprintf(stderr, "COMPILE_ONLY_OK\n"); return 0; }

    const int NV = 64;
    float vbuf[NV][16][4];
    for (int i = 0; i < NV; i++) {
        vbuf[i][0][0] = ((i % 8) * 2.0f / 7.0f) * 2.0f - 1.0f;
        vbuf[i][0][1] = ((i / 8) * 2.0f / 7.0f) * 2.0f - 1.0f;
        vbuf[i][0][2] = 0.0f; vbuf[i][0][3] = 1.0f;
        for (int a = 1; a < 16; a++) {
            vbuf[i][a][0] = ((i * 37 + a * 11) & 255) / 255.0f;
            vbuf[i][a][1] = ((i * 57 + a * 13) & 255) / 255.0f;
            vbuf[i][a][2] = ((i * 97 + a * 17) & 255) / 255.0f;
            vbuf[i][a][3] = 1.0f;
        }
    }
    VkBuffer vbufHandle; VkBufferCreateInfo bci = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
    bci.size = sizeof(vbuf); bci.usage = VK_BUFFER_USAGE_VERTEX_BUFFER_BIT; bci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    vkCreateBuffer(device, &bci, NULL, &vbufHandle);
    VkMemoryRequirements vreq; vkGetBufferMemoryRequirements(device, vbufHandle, &vreq);
    VkDeviceMemory vmem; VkMemoryAllocateInfo vmai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
    vmai.allocationSize = vreq.size; vmai.memoryTypeIndex = hostMem;
    vkAllocateMemory(device, &vmai, NULL, &vmem); vkBindBufferMemory(device, vbufHandle, vmem, 0);
    void *vmap; vkMapMemory(device, vmem, 0, vreq.size, 0, &vmap); memcpy(vmap, vbuf, sizeof(vbuf)); vkUnmapMemory(device, vmem);

    VkImage texImg = VK_NULL_HANDLE; VkDeviceMemory texMem = VK_NULL_HANDLE; VkImageView texView = VK_NULL_HANDLE;
    VkSampler sampler = VK_NULL_HANDLE; VkDescriptorSet dset = VK_NULL_HANDLE; VkDescriptorPool dpool = VK_NULL_HANDLE;
    if (use_tex) {
        uint8_t tex[64 * 64 * 4];
        for (int i = 0; i < 64 * 64; i++) {
            tex[i * 4 + 0] = (uint8_t)((i * 7) & 255);
            tex[i * 4 + 1] = (uint8_t)((i * 3 + 11) & 255);
            tex[i * 4 + 2] = (uint8_t)((i * 5 + 29) & 255);
            tex[i * 4 + 3] = 255;
        }
        VkImageCreateInfo timci = {VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        timci.imageType = VK_IMAGE_TYPE_2D; timci.format = VK_FORMAT_R8G8B8A8_UNORM;
        timci.extent.width = 64; timci.extent.height = 64; timci.extent.depth = 1;
        timci.mipLevels = 1; timci.arrayLayers = 1; timci.samples = VK_SAMPLE_COUNT_1_BIT;
        timci.tiling = VK_IMAGE_TILING_OPTIMAL; timci.usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        timci.sharingMode = VK_SHARING_MODE_EXCLUSIVE; timci.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        vkCreateImage(device, &timci, NULL, &texImg);
        VkMemoryRequirements treq; vkGetImageMemoryRequirements(device, texImg, &treq);
        VkMemoryAllocateInfo tmai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        tmai.allocationSize = treq.size; tmai.memoryTypeIndex = deviceLocal;
        vkAllocateMemory(device, &tmai, NULL, &texMem); vkBindImageMemory(device, texImg, texMem, 0);
        VkBuffer stg; VkBufferCreateInfo stgbci = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        stgbci.size = sizeof(tex); stgbci.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT; stgbci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        vkCreateBuffer(device, &stgbci, NULL, &stg);
        VkMemoryRequirements sreq; vkGetBufferMemoryRequirements(device, stg, &sreq);
        VkDeviceMemory smem; VkMemoryAllocateInfo smai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        smai.allocationSize = sreq.size; smai.memoryTypeIndex = hostMem;
        vkAllocateMemory(device, &smai, NULL, &smem); vkBindBufferMemory(device, stg, smem, 0);
        void *smap; vkMapMemory(device, smem, 0, sreq.size, 0, &smap); memcpy(smap, tex, sizeof(tex)); vkUnmapMemory(device, smem);
        VkCommandPool cpool0; VkCommandPoolCreateInfo cpci0 = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
        cpci0.queueFamilyIndex = qfIndex;
        vkCreateCommandPool(device, &cpci0, NULL, &cpool0);
        VkCommandBuffer cb0; VkCommandBufferAllocateInfo cbaci0 = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
        cbaci0.commandPool = cpool0; cbaci0.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbaci0.commandBufferCount = 1;
        vkAllocateCommandBuffers(device, &cbaci0, &cb0);
        VkCommandBufferBeginInfo cbbi0 = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; cbbi0.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        vkBeginCommandBuffer(cb0, &cbbi0);
        VkImageMemoryBarrier ib = {VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
        ib.srcAccessMask = 0; ib.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        ib.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED; ib.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        ib.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED; ib.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        ib.image = texImg; ib.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT; ib.subresourceRange.levelCount = 1; ib.subresourceRange.layerCount = 1;
        vkCmdPipelineBarrier(cb0, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, 1, &ib);
        VkBufferImageCopy bic = {0}; bic.imageExtent.width = 64; bic.imageExtent.height = 64; bic.imageExtent.depth = 1;
        bic.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT; bic.imageSubresource.layerCount = 1;
        vkCmdCopyBufferToImage(cb0, stg, texImg, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &bic);
        ib.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT; ib.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
        ib.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL; ib.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        vkCmdPipelineBarrier(cb0, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0, 0, NULL, 0, NULL, 1, &ib);
        vkEndCommandBuffer(cb0);
        VkSubmitInfo si0 = {VK_STRUCTURE_TYPE_SUBMIT_INFO}; si0.commandBufferCount = 1; si0.pCommandBuffers = &cb0;
        VkFence fen0; VkFenceCreateInfo fci0 = {VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; vkCreateFence(device, &fci0, NULL, &fen0);
        vkQueueSubmit(queue, 1, &si0, fen0);
        if (vkWaitForFences(device, 1, &fen0, VK_TRUE, 5000000000ULL) != VK_SUCCESS) { fprintf(stderr, "TEX_FENCE_TIMEOUT\n"); return 12; }
        vkDestroyFence(device, fen0, NULL);
        vkFreeCommandBuffers(device, cpool0, 1, &cb0);
        vkDestroyCommandPool(device, cpool0, NULL);
        vkDestroyBuffer(device, stg, NULL); vkFreeMemory(device, smem, NULL);
        VkDescriptorPoolSize psz = {VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1};
        VkDescriptorPoolCreateInfo dpci = {VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
        dpci.poolSizeCount = 1; dpci.pPoolSizes = &psz; dpci.maxSets = 1;
        vkCreateDescriptorPool(device, &dpci, NULL, &dpool);
        VkDescriptorSetAllocateInfo dsai = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
        dsai.descriptorPool = dpool; dsai.descriptorSetCount = 1; dsai.pSetLayouts = &setLayout;
        vkAllocateDescriptorSets(device, &dsai, &dset);
        VkImageViewCreateInfo tivci = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        tivci.image = texImg; tivci.viewType = VK_IMAGE_VIEW_TYPE_2D; tivci.format = VK_FORMAT_R8G8B8A8_UNORM;
        tivci.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT; tivci.subresourceRange.levelCount = 1; tivci.subresourceRange.layerCount = 1;
        vkCreateImageView(device, &tivci, NULL, &texView);
        VkSamplerCreateInfo sci = {VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
        sci.magFilter = VK_FILTER_LINEAR; sci.minFilter = VK_FILTER_LINEAR; sci.mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST;
        sci.addressModeU = VK_SAMPLER_ADDRESS_MODE_REPEAT; sci.addressModeV = VK_SAMPLER_ADDRESS_MODE_REPEAT; sci.addressModeW = VK_SAMPLER_ADDRESS_MODE_REPEAT;
        vkCreateSampler(device, &sci, NULL, &sampler);
        VkDescriptorImageInfo dii = {sampler, texView, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        VkWriteDescriptorSet wr = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
        wr.dstSet = dset; wr.dstBinding = 0; wr.dstArrayElement = 0; wr.descriptorCount = 1;
        wr.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER; wr.pImageInfo = &dii;
        vkUpdateDescriptorSets(device, 1, &wr, 0, NULL);
    }

    VkCommandPool cpool; VkCommandPoolCreateInfo cpci = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; cpci.queueFamilyIndex = qfIndex;
    vkCreateCommandPool(device, &cpci, NULL, &cpool);
    VkCommandBuffer cb; VkCommandBufferAllocateInfo cbaci = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
    cbaci.commandPool = cpool; cbaci.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbaci.commandBufferCount = 1;
    vkAllocateCommandBuffers(device, &cbaci, &cb);
    VkCommandBufferBeginInfo cbbi = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    vkBeginCommandBuffer(cb, &cbbi);
    VkClearValue clear = {{{16, 16, 16, 255}}};
    VkRenderPassBeginInfo rpbi = {VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};
    rpbi.renderPass = renderPass; rpbi.framebuffer = fb; rpbi.renderArea.extent.width = 64; rpbi.renderArea.extent.height = 64;
    rpbi.clearValueCount = 1; rpbi.pClearValues = &clear;
    vkCmdBeginRenderPass(cb, &rpbi, VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);
    VkDeviceSize off = 0; vkCmdBindVertexBuffers(cb, 0, 1, &vbufHandle, &off);
    if (dset != VK_NULL_HANDLE) vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeLayout, 0, 1, &dset, 0, NULL);
    uint8_t pushbytes[128];
    for (int i = 0; i < 128; i += 4) { pushbytes[i] = 0x00; pushbytes[i+1] = 0x00; pushbytes[i+2] = 0x00; pushbytes[i+3] = 0x3F; }
    vkCmdPushConstants(cb, pipeLayout, VK_SHADER_STAGE_FRAGMENT_BIT, 0, 128, pushbytes);
    vkCmdDraw(cb, draw_verts, 1, 0, 0);
    vkCmdEndRenderPass(cb);
    vkEndCommandBuffer(cb);
    VkSubmitInfo si = {VK_STRUCTURE_TYPE_SUBMIT_INFO}; si.commandBufferCount = 1; si.pCommandBuffers = &cb;
    VkFence fen; VkFenceCreateInfo fci = {VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; vkCreateFence(device, &fci, NULL, &fen);
    vkQueueSubmit(queue, 1, &si, fen);
    if (vkWaitForFences(device, 1, &fen, VK_TRUE, 5000000000ULL) != VK_SUCCESS) { fprintf(stderr, "FENCE_TIMEOUT\n"); return 13; }

    VkBuffer rbuf; VkBufferCreateInfo rbci = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
    rbci.size = 64 * 64 * 4; rbci.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT; rbci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    vkCreateBuffer(device, &rbci, NULL, &rbuf);
    VkMemoryRequirements rreq; vkGetBufferMemoryRequirements(device, rbuf, &rreq);
    VkDeviceMemory rmem; VkMemoryAllocateInfo rmai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
    rmai.allocationSize = rreq.size; rmai.memoryTypeIndex = hostMem;
    vkAllocateMemory(device, &rmai, NULL, &rmem); vkBindBufferMemory(device, rbuf, rmem, 0);
    VkCommandBuffer cb2; VkCommandBufferAllocateInfo cbaci2 = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
    cbaci2.commandPool = cpool; cbaci2.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbaci2.commandBufferCount = 1;
    vkAllocateCommandBuffers(device, &cbaci2, &cb2);
    VkCommandBufferBeginInfo cbbi2 = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; cbbi2.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vkBeginCommandBuffer(cb2, &cbbi2);
    VkBufferImageCopy cp = {0}; cp.imageExtent.width = 64; cp.imageExtent.height = 64; cp.imageExtent.depth = 1;
    cp.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT; cp.imageSubresource.layerCount = 1;
    vkCmdCopyImageToBuffer(cb2, img, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, rbuf, 1, &cp);
    vkEndCommandBuffer(cb2);
    VkSubmitInfo si2 = {VK_STRUCTURE_TYPE_SUBMIT_INFO}; si2.commandBufferCount = 1; si2.pCommandBuffers = &cb2;
    VkFence fen2; VkFenceCreateInfo fci2 = {VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; vkCreateFence(device, &fci2, NULL, &fen2);
    vkQueueSubmit(queue, 1, &si2, fen2);
    if (vkWaitForFences(device, 1, &fen2, VK_TRUE, 5000000000ULL) != VK_SUCCESS) { fprintf(stderr, "READOUT_TIMEOUT\n"); return 14; }

    void *rmap; vkMapMemory(device, rmem, 0, 64 * 64 * 4, 0, &rmap);
    FILE *out = fopen(dump, "wb");
    if (out) { fwrite(rmap, 1, 64 * 64 * 4, out); fclose(out); }
    vkUnmapMemory(device, rmem);
    fprintf(stderr, "RENDER_OK dump=%s\n", dump);
    return 0;
}
