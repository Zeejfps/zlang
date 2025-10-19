namespace ParserModule.Nodes;

public sealed class FunctionSignature
{
    public required string Identifier { get; set; }
    public required List<FunctionParameter> Parameters { get; init; }
    public TypeNode? ReturnType { get; init; }
}