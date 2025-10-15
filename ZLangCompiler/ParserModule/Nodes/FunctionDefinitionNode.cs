using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class FunctionParameter
{
    public required string Name { get; init; }
    public required TypeNode Type { get; init; }
}

public sealed class FunctionDefinitionNode : ModuleLevelStatementNode
{
    public required FunctionSignature Signature { get; init; }
    public required BlockStatementNode Body { get; init; }
    
    public override void Accept(IModuleLevelNodeVisitor visitor)
    {
        visitor.VisitFunctionDefinition(this);
    }
}