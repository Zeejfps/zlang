using BenchmarkDotNet.Attributes;

namespace LexerModule.Benchmarks;

[MemoryDiagnoser] // Tracks allocations too
public class LexerBenchmark
{
    private string _filePath;
    private Stream _stream;

    [GlobalSetup]
    public void Setup()
    {
        var assetsPath = Path.Combine(AppContext.BaseDirectory, "Assets");
        _filePath = Path.Combine(assetsPath, "main.z");
    }

    [IterationSetup]
    public void OpenFile()
    {
        // Open fresh stream for each iteration (since streams get consumed)
        _stream = File.OpenRead(_filePath);
    }

    [IterationCleanup]
    public void CloseFile()
    {
        _stream.Dispose();
    }

    [Benchmark]
    public void TokenizeFile()
    {
        var tokens = Lexer.Tokenize(_stream).ToList();
    }
}