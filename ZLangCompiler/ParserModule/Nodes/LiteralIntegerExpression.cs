using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralIntegerExpression : PrimaryExpressionNode
{
    private readonly Token _token;

    public LiteralIntegerExpression(Token token)
    {
        _token = token;
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIntegerNumberExpression(this);
    }
}