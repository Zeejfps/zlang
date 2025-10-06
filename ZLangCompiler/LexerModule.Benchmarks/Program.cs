using BenchmarkDotNet.Running;
using LexerModule.Benchmarks;

BenchmarkRunner.Run<LexerBenchmark>(args: args);