using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class FunctionParameter
{
    public required string Name { get; init; }
    public required TypeNode Type { get; init; }
}

public sealed class FunctionDefinitionNode : ModuleLevelStatementNode
{
    public required string Name { get; init; }
    public required BlockStatementNode Body { get; init; }
    public required TypeNode? ReturnType { get; init; }
    public required List<FunctionParameter> Parameters { get; init; }
    
    public override void Accept(IModuleLevelNodeVisitor visitor)
    {
        visitor.VisitFunctionDefinition(this);
    }
}