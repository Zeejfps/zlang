using LexerModule;

namespace ParserModule.Nodes;

public sealed class IdentifierExpressionNode : AstNode
{
    public Token Token { get; }

    public IdentifierExpressionNode(Token token)
    {
        Token = token;
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIdentifierExpression(this);
    }
}