using LexerModule;

namespace ParserModule.Nodes;

public sealed class IdentifierNode : AstNode
{
    public Token Token { get; }

    public IdentifierNode(Token token)
    {
        Token = token;
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIdentifierNode(this);
    }
}