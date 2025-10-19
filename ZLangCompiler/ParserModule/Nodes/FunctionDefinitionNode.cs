using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class FunctionParameter : AstNode
{
    public required string Name { get; init; }
    public required TypeNode Type { get; init; }
    public override void Accept(IAstNodeVisitor visitor)
    {
        throw new NotImplementedException();
    }
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