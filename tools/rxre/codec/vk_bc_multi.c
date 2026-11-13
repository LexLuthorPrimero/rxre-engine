#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>
#define CHECK(x) do { VkResult _r=(x); if(_r!=VK_SUCCESS){ fprintf(stderr,"Vulkan error %d at %s:%d\n",_r,__FILE__,__LINE__); return 1; } } while(0)

static VkFormat parse_format(const char* s){
    if(!strcmp(s,"bc1")) return VK_FORMAT_BC1_RGB_UNORM_BLOCK;
    if(!strcmp(s,"bc1a")) return VK_FORMAT_BC1_RGBA_UNORM_BLOCK;
    if(!strcmp(s,"bc3")) return VK_FORMAT_BC3_UNORM_BLOCK;
    if(!strcmp(s,"bc4")) return VK_FORMAT_BC4_UNORM_BLOCK;
    if(!strcmp(s,"bc5")) return VK_FORMAT_BC5_UNORM_BLOCK;
    return VK_FORMAT_UNDEFINED;
}
static int bytes_per_block(const char* s){
    if(!strcmp(s,"bc1")||!strcmp(s,"bc1a")||!strcmp(s,"bc4")) return 8;
    return 16;
}

int main(int argc,char**argv){
    if(argc<5){ fprintf(stderr,"usage: %s <format> W H datafile\n",argv[0]); return 1; }
    const char* fmt=argv[1];
    int W=atoi(argv[2]), H=atoi(argv[3]);
    const char* datafile=argv[4];
    VkFormat vkfmt=parse_format(fmt);
    if(vkfmt==VK_FORMAT_UNDEFINED){ fprintf(stderr,"unknown format %s\n",fmt); return 1; }
    int bpb=bytes_per_block(fmt);

    // instance
    VkInstance instance; VkInstanceCreateInfo ici={VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    CHECK(vkCreateInstance(&ici,NULL,&instance));
    uint32_t ndev=0; vkEnumeratePhysicalDevices(instance,&ndev,NULL);
    VkPhysicalDevice* devs=malloc(ndev*sizeof(VkPhysicalDevice));
    vkEnumeratePhysicalDevices(instance,&ndev,devs);
    VkPhysicalDevice phys=NULL;
    for(uint32_t i=0;i<ndev;i++){ VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(devs[i],&p); if(strstr(p.deviceName,"RX 550")) phys=devs[i]; }
    if(!phys) phys=devs[0];
    VkPhysicalDeviceProperties pprops; vkGetPhysicalDeviceProperties(phys,&pprops);
    printf("device: %s\n", pprops.deviceName);
    if(!strstr(pprops.deviceName,"RX 550")){ fprintf(stderr,"ERROR: not RX 550\n"); return 1; }

    // queue
    uint32_t nqf=0; vkGetPhysicalDeviceQueueFamilyProperties(phys,&nqf,NULL);
    VkQueueFamilyProperties* qfp=malloc(nqf*sizeof(VkQueueFamilyProperties));
    vkGetPhysicalDeviceQueueFamilyProperties(phys,&nqf,qfp);
    uint32_t qfi=0; for(uint32_t i=0;i<nqf;i++) if(qfp[i].queueFlags & VK_QUEUE_COMPUTE_BIT){qfi=i;break;}
    float prio=1.0f;
    VkDeviceQueueCreateInfo dqci={VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO}; dqci.queueFamilyIndex=qfi; dqci.queueCount=1; dqci.pQueuePriorities=&prio;
    VkDeviceCreateInfo dci={VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; dci.queueCreateInfoCount=1; dci.pQueueCreateInfos=&dqci;
    VkDevice device; CHECK(vkCreateDevice(phys,&dci,NULL,&device));
    VkQueue queue; vkGetDeviceQueue(device,qfi,0,&queue);

    // shader
    FILE* sf=fopen("/tmp/vktest/shader.spv","rb");
    fseek(sf,0,SEEK_END); long ssz=ftell(sf); fseek(sf,0,SEEK_SET);
    char* scode=malloc(ssz); fread(scode,1,ssz,sf); fclose(sf);
    VkShaderModuleCreateInfo smci={VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO}; smci.codeSize=ssz; smci.pCode=(const uint32_t*)scode;
    VkShaderModule shader; CHECK(vkCreateShaderModule(device,&smci,NULL,&shader));

    int ph=(H+3)/4*4, pw=(W+3)/4*4;
    int nblocks=(ph/4)*(pw/4);
    int datasize=nblocks*bpb;

    // read data file
    FILE* df=fopen(datafile,"rb"); fseek(df,0,SEEK_END); long dsz=ftell(df); fseek(df,0,SEEK_SET);
    if(dsz < datasize){ fprintf(stderr,"data file too small: %ld < %d\n",dsz,datasize); return 1; }
    char* data=malloc(datasize); fread(data,1,datasize,df); fclose(df);

    // image
    VkImageCreateInfo ici2={VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO}; ici2.imageType=VK_IMAGE_TYPE_2D; ici2.format=vkfmt;
    ici2.extent.width=W; ici2.extent.height=H; ici2.extent.depth=1; ici2.mipLevels=1; ici2.arrayLayers=1;
    ici2.samples=VK_SAMPLE_COUNT_1_BIT; ici2.tiling=VK_IMAGE_TILING_OPTIMAL;
    ici2.usage=VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT; ici2.sharingMode=VK_SHARING_MODE_EXCLUSIVE; ici2.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
    VkImage image; CHECK(vkCreateImage(device,&ici2,NULL,&image));
    VkMemoryRequirements mr; vkGetImageMemoryRequirements(device,image,&mr);
    VkPhysicalDeviceMemoryProperties mprops; vkGetPhysicalDeviceMemoryProperties(phys,&mprops);
    uint32_t mt=0; for(uint32_t i=0;i<mprops.memoryTypeCount;i++) if((mr.memoryTypeBits&(1<<i))&&(mprops.memoryTypes[i].propertyFlags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)){mt=i;break;}
    VkMemoryAllocateInfo mai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; mai.allocationSize=mr.size; mai.memoryTypeIndex=mt;
    VkDeviceMemory imgmem; CHECK(vkAllocateMemory(device,&mai,NULL,&imgmem)); CHECK(vkBindImageMemory(device,image,imgmem,0));
    // staging
    VkBufferCreateInfo bci={VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; bci.size=datasize; bci.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT; bci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
    VkBuffer staging; CHECK(vkCreateBuffer(device,&bci,NULL,&staging));
    VkMemoryRequirements bmr; vkGetBufferMemoryRequirements(device,staging,&bmr);
    uint32_t hmt=0; for(uint32_t i=0;i<mprops.memoryTypeCount;i++) if((bmr.memoryTypeBits&(1<<i))&&(mprops.memoryTypes[i].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))==(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)){hmt=i;break;}
    VkMemoryAllocateInfo bmai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; bmai.allocationSize=bmr.size; bmai.memoryTypeIndex=hmt;
    VkDeviceMemory stgmem; CHECK(vkAllocateMemory(device,&bmai,NULL,&stgmem)); CHECK(vkBindBufferMemory(device,staging,stgmem,0));
    void* stgptr; CHECK(vkMapMemory(device,stgmem,0,bmr.size,0,&stgptr));
    memcpy(stgptr,data,datasize); vkUnmapMemory(device,stgmem);
    // output buffer
    VkBufferCreateInfo obci={VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; obci.size=W*H*4*sizeof(float); obci.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT; obci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
    VkBuffer outbuf; CHECK(vkCreateBuffer(device,&obci,NULL,&outbuf));
    VkMemoryRequirements omr; vkGetBufferMemoryRequirements(device,outbuf,&omr);
    uint32_t omt=0; for(uint32_t i=0;i<mprops.memoryTypeCount;i++) if((omr.memoryTypeBits&(1<<i))&&(mprops.memoryTypes[i].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))==(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)){omt=i;break;}
    VkMemoryAllocateInfo omai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; omai.allocationSize=omr.size; omai.memoryTypeIndex=omt;
    VkDeviceMemory outmem; CHECK(vkAllocateMemory(device,&omai,NULL,&outmem)); CHECK(vkBindBufferMemory(device,outbuf,outmem,0));
    // image view
    VkImageViewCreateInfo ivci={VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO}; ivci.image=image; ivci.viewType=VK_IMAGE_VIEW_TYPE_2D; ivci.format=vkfmt;
    ivci.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT; ivci.subresourceRange.baseMipLevel=0; ivci.subresourceRange.levelCount=1; ivci.subresourceRange.baseArrayLayer=0; ivci.subresourceRange.layerCount=1;
    VkImageView imgview; CHECK(vkCreateImageView(device,&ivci,NULL,&imgview));
    // sampler
    VkSamplerCreateInfo sci={VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO}; sci.magFilter=VK_FILTER_NEAREST; sci.minFilter=VK_FILTER_NEAREST; sci.mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST;
    sci.addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE; sci.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE; sci.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    VkSampler sampler; CHECK(vkCreateSampler(device,&sci,NULL,&sampler));
    // descriptor layout
    VkDescriptorSetLayoutBinding binds[2]; memset(binds,0,sizeof(binds));
    binds[0].binding=0; binds[0].descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER; binds[0].descriptorCount=1; binds[0].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    binds[1].binding=1; binds[1].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; binds[1].descriptorCount=1; binds[1].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    VkDescriptorSetLayoutCreateInfo dslci={VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO}; dslci.bindingCount=2; dslci.pBindings=binds;
    VkDescriptorSetLayout dsl; CHECK(vkCreateDescriptorSetLayout(device,&dslci,NULL,&dsl));
    VkPushConstantRange pcr={VK_SHADER_STAGE_COMPUTE_BIT,0,8};
    VkPipelineLayoutCreateInfo plci={VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO}; plci.setLayoutCount=1; plci.pSetLayouts=&dsl; plci.pushConstantRangeCount=1; plci.pPushConstantRanges=&pcr;
    VkPipelineLayout pl; CHECK(vkCreatePipelineLayout(device,&plci,NULL,&pl));
    VkComputePipelineCreateInfo cpci={VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
    cpci.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO; cpci.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT; cpci.stage.module=shader; cpci.stage.pName="main"; cpci.layout=pl;
    VkPipeline pipe; CHECK(vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&cpci,NULL,&pipe));
    // descriptor pool
    VkDescriptorPoolSize psz[2]; psz[0].type=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER; psz[0].descriptorCount=1; psz[1].type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; psz[1].descriptorCount=1;
    VkDescriptorPoolCreateInfo dpci={VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO}; dpci.maxSets=1; dpci.poolSizeCount=2; dpci.pPoolSizes=psz;
    VkDescriptorPool dp; CHECK(vkCreateDescriptorPool(device,&dpci,NULL,&dp));
    VkDescriptorSetAllocateInfo dsai={VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO}; dsai.descriptorPool=dp; dsai.descriptorSetCount=1; dsai.pSetLayouts=&dsl;
    VkDescriptorSet ds; CHECK(vkAllocateDescriptorSets(device,&dsai,&ds));
    VkDescriptorImageInfo dii={sampler,imgview,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    VkDescriptorBufferInfo dbi={outbuf,0,VK_WHOLE_SIZE};
    VkWriteDescriptorSet w[2]; memset(w,0,sizeof(w));
    w[0].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; w[0].dstSet=ds; w[0].dstBinding=0; w[0].descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER; w[0].descriptorCount=1; w[0].pImageInfo=&dii;
    w[1].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; w[1].dstSet=ds; w[1].dstBinding=1; w[1].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; w[1].descriptorCount=1; w[1].pBufferInfo=&dbi;
    vkUpdateDescriptorSets(device,2,w,0,NULL);
    // command
    VkCommandPoolCreateInfo cpci2={VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; cpci2.queueFamilyIndex=qfi; cpci2.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    VkCommandPool cmdpool; CHECK(vkCreateCommandPool(device,&cpci2,NULL,&cmdpool));
    VkCommandBufferAllocateInfo cbai={VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; cbai.commandPool=cmdpool; cbai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbai.commandBufferCount=1;
    VkCommandBuffer cmd; CHECK(vkAllocateCommandBuffers(device,&cbai,&cmd));
    VkCommandBufferBeginInfo cbbi={VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; cbbi.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    CHECK(vkBeginCommandBuffer(cmd,&cbbi));
    VkImageMemoryBarrier imb={VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER}; imb.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED; imb.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    imb.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED; imb.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED; imb.image=image; imb.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT; imb.subresourceRange.baseMipLevel=0; imb.subresourceRange.levelCount=1; imb.subresourceRange.baseArrayLayer=0; imb.subresourceRange.layerCount=1;
    imb.srcAccessMask=0; imb.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&imb);
    VkBufferImageCopy bic={0}; bic.imageSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT; bic.imageSubresource.mipLevel=0; bic.imageSubresource.baseArrayLayer=0; bic.imageSubresource.layerCount=1;
    bic.imageExtent.width=W; bic.imageExtent.height=H; bic.imageExtent.depth=1;
    vkCmdCopyBufferToImage(cmd,staging,image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&bic);
    imb.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL; imb.newLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL; imb.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT; imb.dstAccessMask=VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,NULL,0,NULL,1,&imb);
    vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipe);
    vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pl,0,1,&ds,0,NULL);
    int pc[2]={W,H}; vkCmdPushConstants(cmd,pl,VK_SHADER_STAGE_COMPUTE_BIT,0,8,pc);
    vkCmdDispatch(cmd,(W+3)/4,(H+3)/4,1);
    VkBufferMemoryBarrier bmb={VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER}; bmb.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT; bmb.dstAccessMask=VK_ACCESS_HOST_READ_BIT; bmb.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED; bmb.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED; bmb.buffer=outbuf; bmb.offset=0; bmb.size=VK_WHOLE_SIZE;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,0,NULL,1,&bmb,0,NULL);
    CHECK(vkEndCommandBuffer(cmd));
    VkSubmitInfo si={VK_STRUCTURE_TYPE_SUBMIT_INFO}; si.commandBufferCount=1; si.pCommandBuffers=&cmd;
    VkFence fence; VkFenceCreateInfo fci={VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; CHECK(vkCreateFence(device,&fci,NULL,&fence));
    CHECK(vkQueueSubmit(queue,1,&si,fence)); CHECK(vkWaitForFences(device,1,&fence,VK_TRUE,UINT64_MAX));
    void* outptr; CHECK(vkMapMemory(device,outmem,0,omr.size,0,&outptr));
    float* fptr=(float*)outptr;
    FILE* go=fopen("/tmp/gpu_out.bin","wb"); fwrite(fptr,1,W*H*4*sizeof(float),go); fclose(go);
    printf("GPU sampled pixel[0]: R=%.3f G=%.3f B=%.3f A=%.3f\n", fptr[0], fptr[1], fptr[2], fptr[3]);
    vkUnmapMemory(device,outmem);
    printf("SUCCESS format=%s\n", fmt);
    return 0;
}
