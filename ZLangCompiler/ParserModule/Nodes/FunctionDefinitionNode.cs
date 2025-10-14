namespace ParserModule.Nodes;

public sealed class FunctionDefinitionNode : AstNode
{
    public required string Name { get; init; }
    public required BlockStatementNode Body { get; init; }
    public required TypeNode? ReturnType { get; init; }
    public required List<ParameterNode> Parameters { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitFunctionDeclarationNode(this);
    }
}