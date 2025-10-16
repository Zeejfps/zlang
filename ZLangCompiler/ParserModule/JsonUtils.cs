using System.Text.Json.Nodes;

namespace ParserModule;

public static class JsonUtils
{
    public static void Merge(this JsonObject target, JsonObject source)
    {
        foreach (var kvp in source)
        {
            if (kvp.Value is JsonObject sourceObj)
            {
                if (target[kvp.Key] is JsonObject targetObj)
                {
                    // Recursively merge nested objects
                    targetObj.Merge(sourceObj);
                }
                else
                {
                    target[kvp.Key] = sourceObj.DeepClone();
                }
            }
            else if (kvp.Value is JsonArray sourceArray)
            {
                if (target[kvp.Key] is JsonArray targetArray)
                {
                    MergeArrays(targetArray, sourceArray);
                }
                else
                {
                    target[kvp.Key] = sourceArray.DeepClone();
                }
            }
            else
            {
                // Replace primitives or nulls
                target[kvp.Key] = kvp.Value?.DeepClone();
            }
        }
    }

    private static void MergeArrays(JsonArray targetArray, JsonArray sourceArray)
    {
        foreach (var item in sourceArray)
        {
            bool exists = false;

            // Compare using JSON string representation for simplicity
            var sourceStr = item?.ToJsonString();

            foreach (var targetItem in targetArray)
            {
                if (targetItem?.ToJsonString() == sourceStr)
                {
                    exists = true;
                    break;
                }
            }

            if (!exists)
                targetArray.Add(item?.DeepClone());
        }
    }
}