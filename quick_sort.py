def quick_sort(arr, low=0, high=None):
    """
    快速排序算法（原地排序）
    
    :param arr: 待排序的列表
    :param low: 起始索引
    :param high: 结束索引
    """
    if high is None:
        high = len(arr) - 1
    
    if low < high:
        # 分区操作，获取基准元素的最终位置
        pivot_index = partition(arr, low, high)
        
        # 递归排序基准左右两边的子数组
        quick_sort(arr, low, pivot_index - 1)
        quick_sort(arr, pivot_index + 1, high)


def partition(arr, low, high):
    """
    分区函数：选择基准元素，将小于基准的放左边，大于基准的放右边
    
    这里选择最后一个元素作为基准（pivot）
    """
    pivot = arr[high]  # 选择最后一个元素作为基准
    i = low - 1        # i 指向小于基准的元素的最后一个位置
    
    for j in range(low, high):
        # 如果当前元素小于或等于基准
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]  # 交换
    
    # 将基准放到正确的位置（i+1）
    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


def quick_sort_simple(arr):
    """
    快速排序的简洁实现（非原地，返回新列表）
    适合教学和理解算法思想
    """
    if len(arr) <= 1:
        return arr
    
    pivot = arr[len(arr) // 2]  # 选择中间元素作为基准
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    return quick_sort_simple(left) + middle + quick_sort_simple(right)


if __name__ == "__main__":
    # 测试
    test_arr = [64, 34, 25, 12, 22, 11, 90]
    print("原始数组:", test_arr)
    
    # 原地排序版本
    arr1 = test_arr.copy()
    quick_sort(arr1)
    print("原地排序后:", arr1)
    
    # 简洁版本
    arr2 = test_arr.copy()
    sorted_arr = quick_sort_simple(arr2)
    print("简洁版排序后:", sorted_arr)
