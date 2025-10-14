using LexerModule;

namespace ParserModule.Nodes.Expressions;

public sealed class IdentifierExpressionNode : ExpressionNode
{
    public Token Token { get; }
    public string Name { get; }

    public IdentifierExpressionNode(Token token)
    {
        Token = token;
        Name = token.Lexeme;
    }

    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitIdentifier(this);
    }
}