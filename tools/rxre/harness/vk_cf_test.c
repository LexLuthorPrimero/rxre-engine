// vk_cf_test — headless Vulkan compute harness (POLARIS-028..039).
// Usage: vk_cf_test <spv> [num_elements=64] [has_input=0] [print_count=16]
//   has_input=1: binding-0 storage buffer filled indata[i]=i (uint32)
// Prints "DEVICE: <name>" and "RESULTS: <uint32...>".
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <vulkan/vulkan.h>

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "Usage: %s <spv> [num_elements] [has_input] [print_count]\n", argv[0]); return 1; }
    const char *shader_path = argv[1];
    uint32_t num_elements = (argc > 2) ? (uint32_t)atoi(argv[2]) : 64;
    int has_input = (argc > 3) ? atoi(argv[3]) : 0;
    uint32_t print_count = (argc > 4) ? (uint32_t)atoi(argv[4]) : 16;
    int no_run = 0;
    for (int i = 5; i < argc; i++) if (!strcmp(argv[i], "--no-run")) no_run = 1;

    VkInstance instance;
    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName = "vk_cf_test"; app.apiVersion = VK_API_VERSION_1_0;
    VkInstanceCreateInfo ici = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    ici.pApplicationInfo = &app;
    vkCreateInstance(&ici, NULL, &instance);

    uint32_t devCount = 0;
    vkEnumeratePhysicalDevices(instance, &devCount, NULL);
    VkPhysicalDevice *devs = malloc(devCount * sizeof(VkPhysicalDevice));
    vkEnumeratePhysicalDevices(instance, &devCount, devs);
    VkPhysicalDevice pdev = VK_NULL_HANDLE;
    for (uint32_t i = 0; i < devCount; i++) {
        VkPhysicalDeviceProperties pr; vkGetPhysicalDeviceProperties(devs[i], &pr);
        if (pr.vendorID == 0x1002u) { pdev = devs[i]; printf("DEVICE: %s\n", pr.deviceName); }
    }
    free(devs);
    if (pdev == VK_NULL_HANDLE) { fprintf(stderr, "No AMD GPU\n"); return 1; }

    uint32_t qfCount = 0; vkGetPhysicalDeviceQueueFamilyProperties(pdev, &qfCount, NULL);
    VkQueueFamilyProperties *qf = malloc(qfCount * sizeof(VkQueueFamilyProperties));
    vkGetPhysicalDeviceQueueFamilyProperties(pdev, &qfCount, qf);
    uint32_t qfIndex = 0;
    for (uint32_t i = 0; i < qfCount; i++) if (qf[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { qfIndex = i; break; }
    free(qf);

    VkPhysicalDeviceMemoryProperties memProps; vkGetPhysicalDeviceMemoryProperties(pdev, &memProps);
    uint32_t memTypeIndex = UINT32_MAX;
    for (uint32_t i = 0; i < memProps.memoryTypeCount; i++) {
        if ((memProps.memoryTypes[i].propertyFlags & (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) ==
            (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) { memTypeIndex = i; break; }
    }

    VkDevice device; float qp = 1.0f;
    VkDeviceQueueCreateInfo dqci = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    dqci.queueFamilyIndex = qfIndex; dqci.queueCount = 1; dqci.pQueuePriorities = &qp;
    VkDeviceCreateInfo dci = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    dci.queueCreateInfoCount = 1; dci.pQueueCreateInfos = &dqci;
    vkCreateDevice(pdev, &dci, NULL, &device);
    VkQueue queue; vkGetDeviceQueue(device, qfIndex, 0, &queue);

    FILE *f = fopen(shader_path, "rb");
    if (!f) { fprintf(stderr, "Cannot open shader: %s\n", shader_path); return 1; }
    fseek(f, 0, SEEK_END); size_t sz = ftell(f); fseek(f, 0, SEEK_SET);
    char *code = malloc(sz); fread(code, 1, sz, f); fclose(f);
    VkShaderModule mod; VkShaderModuleCreateInfo smci = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
    smci.codeSize = sz; smci.pCode = (const uint32_t *)code;
    if (vkCreateShaderModule(device, &smci, NULL, &mod) != VK_SUCCESS) { fprintf(stderr, "BAD_MODULE\n"); return 2; }

    VkDescriptorSetLayoutBinding binds[2] = {0};
    uint32_t nbinds = 0;
    if (has_input) { binds[nbinds].binding = 0; binds[nbinds].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; binds[nbinds].descriptorCount = 1; binds[nbinds].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT; nbinds++; }
    binds[nbinds].binding = 1; binds[nbinds].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; binds[nbinds].descriptorCount = 1; binds[nbinds].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT; nbinds++;
    VkDescriptorSetLayoutCreateInfo dslci = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    dslci.bindingCount = nbinds; dslci.pBindings = binds;
    VkDescriptorSetLayout setLayout; vkCreateDescriptorSetLayout(device, &dslci, NULL, &setLayout);
    VkPipelineLayoutCreateInfo plci = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    plci.setLayoutCount = 1; plci.pSetLayouts = &setLayout;
    VkPipelineLayout pipeLayout; vkCreatePipelineLayout(device, &plci, NULL, &pipeLayout);

    VkComputePipelineCreateInfo cpci = {VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
    cpci.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    cpci.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT; cpci.stage.module = mod; cpci.stage.pName = "main";
    cpci.layout = pipeLayout;
    VkPipeline pipeline;
    if (vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &cpci, NULL, &pipeline) != VK_SUCCESS) { fprintf(stderr, "BAD_PIPELINE\n"); return 3; }
    if (no_run) { fprintf(stderr, "COMPILE_ONLY_OK\n"); return 0; }

    VkBuffer inbuf = VK_NULL_HANDLE, outbuf; VkDeviceMemory inmem = VK_NULL_HANDLE, outmem;
    VkDeviceSize bytes = num_elements * sizeof(uint32_t);
    if (has_input) {
        VkBufferCreateInfo bci = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        bci.size = bytes; bci.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT; bci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        vkCreateBuffer(device, &bci, NULL, &inbuf);
        VkMemoryRequirements r; vkGetBufferMemoryRequirements(device, inbuf, &r);
        VkMemoryAllocateInfo mai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; mai.allocationSize = r.size; mai.memoryTypeIndex = memTypeIndex;
        vkAllocateMemory(device, &mai, NULL, &inmem); vkBindBufferMemory(device, inbuf, inmem, 0);
        void *m; vkMapMemory(device, inmem, 0, r.size, 0, &m);
        for (uint32_t i = 0; i < num_elements; i++) ((uint32_t *)m)[i] = i;
        vkUnmapMemory(device, inmem);
    }
    {
        VkBufferCreateInfo bci = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        bci.size = bytes; bci.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT; bci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        vkCreateBuffer(device, &bci, NULL, &outbuf);
        VkMemoryRequirements r; vkGetBufferMemoryRequirements(device, outbuf, &r);
        VkMemoryAllocateInfo mai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; mai.allocationSize = r.size; mai.memoryTypeIndex = memTypeIndex;
        vkAllocateMemory(device, &mai, NULL, &outmem); vkBindBufferMemory(device, outbuf, outmem, 0);
    }

    VkDescriptorPoolSize psz = {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 2};
    VkDescriptorPoolCreateInfo dpci = {VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
    dpci.poolSizeCount = 1; dpci.pPoolSizes = &psz; dpci.maxSets = 1;
    VkDescriptorPool dpool; vkCreateDescriptorPool(device, &dpci, NULL, &dpool);
    VkDescriptorSet dset; VkDescriptorSetAllocateInfo dsai = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
    dsai.descriptorPool = dpool; dsai.descriptorSetCount = 1; dsai.pSetLayouts = &setLayout;
    vkAllocateDescriptorSets(device, &dsai, &dset);
    VkDescriptorBufferInfo infos[2]; VkWriteDescriptorSet wrs[2]; memset(wrs, 0, sizeof(wrs));
    uint32_t wi = 0;
    if (has_input) { infos[wi].buffer = inbuf; infos[wi].offset = 0; infos[wi].range = bytes;
        wrs[wi].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; wrs[wi].dstSet = dset; wrs[wi].dstBinding = 0; wrs[wi].descriptorCount = 1; wrs[wi].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; wrs[wi].pBufferInfo = &infos[wi]; wi++; }
    infos[wi].buffer = outbuf; infos[wi].offset = 0; infos[wi].range = bytes;
    wrs[wi].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; wrs[wi].dstSet = dset; wrs[wi].dstBinding = 1; wrs[wi].descriptorCount = 1; wrs[wi].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; wrs[wi].pBufferInfo = &infos[wi];
    vkUpdateDescriptorSets(device, has_input ? 2 : 1, wrs, 0, NULL);

    VkCommandPool cpool; VkCommandPoolCreateInfo cpci2 = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; cpci2.queueFamilyIndex = qfIndex;
    vkCreateCommandPool(device, &cpci2, NULL, &cpool);
    VkCommandBuffer cb; VkCommandBufferAllocateInfo cbaci = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
    cbaci.commandPool = cpool; cbaci.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbaci.commandBufferCount = 1;
    vkAllocateCommandBuffers(device, &cbaci, &cb);
    VkCommandBufferBeginInfo cbbi = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    vkBeginCommandBuffer(cb, &cbbi);
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
    vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipeLayout, 0, 1, &dset, 0, NULL);
    vkCmdDispatch(cb, (num_elements + 63) / 64, 1, 1);
    vkEndCommandBuffer(cb);
    VkSubmitInfo si = {VK_STRUCTURE_TYPE_SUBMIT_INFO}; si.commandBufferCount = 1; si.pCommandBuffers = &cb;
    VkFence fen; VkFenceCreateInfo fci = {VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; vkCreateFence(device, &fci, NULL, &fen);
    vkQueueSubmit(queue, 1, &si, fen);
    if (vkWaitForFences(device, 1, &fen, VK_TRUE, 10000000000ULL) != VK_SUCCESS) { fprintf(stderr, "FENCE_TIMEOUT\n"); return 4; }

    void *m; vkMapMemory(device, outmem, 0, bytes, 0, &m);
    printf("RESULTS:");
    uint32_t lim = print_count < num_elements ? print_count : num_elements;
    for (uint32_t i = 0; i < lim; i++) printf(" %u", ((uint32_t *)m)[i]);
    printf("\n");
    vkUnmapMemory(device, outmem);
    return 0;
}
