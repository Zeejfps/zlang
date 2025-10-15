namespace ParserModule.Nodes;

public sealed class FunctionSignature
{
    public required string Name { get; init; }
    public required List<FunctionParameter> Parameters { get; init; }
    public TypeNode? ReturnType { get; init; }
}