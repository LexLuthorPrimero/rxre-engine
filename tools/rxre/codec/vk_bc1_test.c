#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

int main() {
    VkInstance instance;
    VkInstanceCreateInfo ici={VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    if(vkCreateInstance(&ici,NULL,&instance)!=VK_SUCCESS){ fprintf(stderr,"instance fail\n"); return 1; }

    uint32_t ndev=0;
    vkEnumeratePhysicalDevices(instance,&ndev,NULL);
    VkPhysicalDevice* devs=malloc(ndev*sizeof(VkPhysicalDevice));
    vkEnumeratePhysicalDevices(instance,&ndev,devs);
    VkPhysicalDevice chosen=NULL;
    for(uint32_t i=0;i<ndev;i++){
        VkPhysicalDeviceProperties p;
        vkGetPhysicalDeviceProperties(devs[i],&p);
        printf("device %u: %s\n", i, p.deviceName);
        if(strstr(p.deviceName,"RX 550") || strstr(p.deviceName,"Polaris")) chosen=devs[i];
    }
    if(!chosen){ chosen=devs[0]; printf("fallback to device 0\n"); }
    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(chosen,&props);
    printf("chosen: %s\n", props.deviceName);

    const VkFormat fmts[] = {VK_FORMAT_BC1_RGB_UNORM_BLOCK, VK_FORMAT_BC1_RGBA_UNORM_BLOCK,
                             VK_FORMAT_BC3_UNORM_BLOCK, VK_FORMAT_BC4_UNORM_BLOCK, VK_FORMAT_BC5_UNORM_BLOCK};
    const char* names[] = {"BC1_RGB","BC1_RGBA","BC3","BC4","BC5"};
    for(int i=0;i<5;i++){
        VkFormatProperties fp;
        vkGetPhysicalDeviceFormatProperties(chosen, fmts[i], &fp);
        printf("%s: optimal=0x%x sampled=%s\n", names[i], fp.optimalTilingFeatures,
               (fp.optimalTilingFeatures & VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT)?"YES":"NO");
    }

    vkDestroyInstance(instance,NULL);
    printf("SUCCESS\n");
    return 0;
}
