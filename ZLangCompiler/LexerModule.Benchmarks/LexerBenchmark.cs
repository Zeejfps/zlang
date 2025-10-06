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
        _filePath = "/Users/zee-seriesai/src/zlang/prototyping/src/main.z";
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