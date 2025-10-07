namespace ParserModule.Tests;

public static class Extensions
{
    public static void AssertIsType<T>(this object obj, out T cast)
    {
        Assert.That(obj, Is.TypeOf<T>(), $"Expected object to be of type {typeof(T).Name}, but was {obj?.GetType().Name ?? "null"}.");
        cast = (T)obj;
    }
}