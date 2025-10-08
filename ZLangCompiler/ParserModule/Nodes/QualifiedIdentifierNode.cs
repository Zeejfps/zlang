namespace ParserModule.Nodes;

public sealed class QualifiedIdentifierNode : AstNode
{
    public required List<string> Parts { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitQualifiedIdentifierNode(this);
    }
}